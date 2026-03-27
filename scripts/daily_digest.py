#!/usr/bin/env python3
"""
VLA / Physical AI Daily Paper Digest
=====================================
arXiv, Google Scholar, Google News에서 VLA·Physical AI 관련 논문/뉴스를 수집하고
Claude API로 요약한 뒤 GitHub Issue로 발행합니다.

Twitter/X는 API 비용 문제로 제외 — 대안으로 Semantic Scholar를 사용합니다.
"""

import os
import json
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional

# ── 설정 ──────────────────────────────────────────────
SEARCH_QUERIES = [
    "vision language action model",
    "VLA robot",
    "physical AI robotics",
    "physics-informed robot learning",
    "Hamiltonian neural network robot",
    "embodied AI manipulation",
]

# 각 소스별 최대 수집 수
MAX_ARXIV = 15
MAX_SCHOLAR = 10
MAX_NEWS = 10
MAX_SEMANTIC = 10

KST = timezone(timedelta(hours=9))


# ── arXiv API ─────────────────────────────────────────
def search_arxiv() -> list[dict]:
    """arXiv API로 최근 7일 내 관련 논문 검색."""
    papers = []
    seen_ids = set()

    for query in SEARCH_QUERIES[:3]:  # 상위 3개 쿼리만 사용 (rate limit 고려)
        time.sleep(3)  # arXiv rate limit 방지
        params = urllib.parse.urlencode({
            "search_query": f'all:"{query}" AND (cat:cs.RO OR cat:cs.AI OR cat:cs.LG OR cat:cs.CV)',
            "start": 0,
            "max_results": MAX_ARXIV,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        url = f"http://export.arxiv.org/api/query?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VLA-Digest/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                root = ET.fromstring(resp.read())

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                arxiv_id = entry.find("atom:id", ns).text.strip().split("/abs/")[-1]
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                title = " ".join(entry.find("atom:title", ns).text.split())
                summary = " ".join(entry.find("atom:summary", ns).text.split())
                published = entry.find("atom:published", ns).text[:10]
                authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
                link = f"https://arxiv.org/abs/{arxiv_id}"

                categories = [c.get("term") for c in entry.findall("atom:category", ns)]

                papers.append({
                    "source": "arXiv",
                    "title": title,
                    "authors": ", ".join(authors[:5]) + ("..." if len(authors) > 5 else ""),
                    "abstract": summary[:500],
                    "url": link,
                    "date": published,
                    "categories": ", ".join(categories[:3]),
                    "venue": "arXiv preprint",
                })
        except Exception as e:
            print(f"[arXiv] Query '{query}' failed: {e}")

    return papers


# ── Semantic Scholar API (Twitter/X 대체) ─────────────
def search_semantic_scholar() -> list[dict]:
    """Semantic Scholar API로 최근 관련 논문 검색 (무료, rate limit 관대)."""
    papers = []
    seen_ids = set()

    for query in SEARCH_QUERIES[:2]:
        time.sleep(3)  # rate limit 방지
        params = urllib.parse.urlencode({
            "query": query,
            "limit": MAX_SEMANTIC,
            "fields": "title,authors,abstract,url,publicationDate,externalIds,venue,publicationVenue",
            "year": f"{datetime.now().year - 1}-",
            "sort": "publicationDate:desc",
        })
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VLA-Digest/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            for paper in data.get("data", []):
                pid = paper.get("paperId", "")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                ext = paper.get("externalIds", {})
                arxiv_id = ext.get("ArXiv")
                link = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else paper.get("url", "")

                authors = [a.get("name", "") for a in (paper.get("authors") or [])[:5]]

                # 학회/venue 정보 추출
                venue = paper.get("venue", "")
                pub_venue = paper.get("publicationVenue", {})
                venue_name = venue or (pub_venue.get("name", "") if pub_venue else "")

                papers.append({
                    "source": "Semantic Scholar",
                    "title": paper.get("title", "Untitled"),
                    "authors": ", ".join(authors),
                    "abstract": (paper.get("abstract") or "")[:500],
                    "url": link,
                    "date": paper.get("publicationDate", ""),
                    "categories": "",
                    "venue": venue_name,
                })
        except Exception as e:
            print(f"[Semantic Scholar] Query '{query}' failed: {e}")

    return papers


# ── Google News RSS ───────────────────────────────────
def search_google_news() -> list[dict]:
    """Google News RSS 피드로 관련 뉴스 검색."""
    articles = []
    seen_titles = set()

    news_queries = [
        "VLA model robot",
        "physical AI robotics",
        "embodied AI robot manipulation",
    ]

    for query in news_queries:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}+when:7d&hl=en&gl=US&ceid=US:en"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VLA-Digest/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                root = ET.fromstring(resp.read())

            for item in root.findall(".//item")[:MAX_NEWS]:
                title = item.find("title").text or ""
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                link = item.find("link").text or ""
                pub_date = item.find("pubDate").text or ""
                source = item.find("source")
                source_name = source.text if source is not None else ""

                # pubDate 파싱 (RFC 822 → YYYY-MM-DD)
                date_str = ""
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub_date)
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = pub_date[:16]

                articles.append({
                    "source": f"News ({source_name})",
                    "title": title,
                    "authors": source_name,
                    "abstract": "",
                    "url": link,
                    "date": date_str,
                    "categories": "",
                    "venue": source_name,
                })
        except Exception as e:
            print(f"[News] Query '{query}' failed: {e}")

    return articles


# ── Google Scholar (scholarly) ────────────────────────
def search_google_scholar() -> list[dict]:
    """scholarly 라이브러리로 Google Scholar 검색. 실패 시 빈 리스트 반환."""
    try:
        from scholarly import scholarly as scholar_api
    except ImportError:
        print("[Scholar] scholarly not installed, skipping")
        return []

    papers = []
    seen_titles = set()

    for query in SEARCH_QUERIES[:2]:
        try:
            results = scholar_api.search_pubs(query, year_low=datetime.now().year - 1)
            for i, result in enumerate(results):
                if i >= MAX_SCHOLAR:
                    break

                bib = result.get("bib", {})
                title = bib.get("title", "")
                if title.lower() in seen_titles:
                    continue
                seen_titles.add(title.lower())

                papers.append({
                    "source": "Google Scholar",
                    "title": title,
                    "authors": bib.get("author", ""),
                    "abstract": bib.get("abstract", "")[:500],
                    "url": result.get("pub_url", result.get("eprint_url", "")),
                    "date": bib.get("pub_year", ""),
                    "categories": bib.get("venue", ""),
                    "venue": bib.get("venue", ""),
                })
        except Exception as e:
            print(f"[Scholar] Query '{query}' failed: {e}")
            break  # rate limit 가능성 → 중단

    return papers


# ── Claude API 요약 ───────────────────────────────────
def summarize_with_claude(papers: list[dict]) -> str:
    """Claude API로 수집된 논문/뉴스 다이제스트 생성."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_format(papers)

    paper_text = ""
    for i, p in enumerate(papers, 1):
        paper_text += f"\n---\n[{i}] ({p['source']}) {p['title']}\n"
        paper_text += f"Authors: {p['authors']}\n"
        paper_text += f"Date: {p['date']}\n"
        paper_text += f"Venue/Conference: {p.get('venue', 'N/A')}\n"
        paper_text += f"URL: {p['url']}\n"
        if p["abstract"]:
            paper_text += f"Abstract: {p['abstract']}\n"

    prompt = f"""다음은 오늘 수집된 VLA(Vision-Language-Action) 모델 및 Physical AI 관련 논문과 뉴스입니다.

{paper_text}

위 내용을 기반으로 GitHub Issue용 일일 다이제스트를 작성해주세요:

1. **오늘의 하이라이트** (가장 중요한 2-3개를 선정해 각각 2-3문장으로 핵심 요약)
2. **논문 목록** (아래 형식을 반드시 따를 것):
   - 제목 (링크 포함)
   - 저자
   - **학회/출판처** (예: CoRL 2025, ICRA 2026, arXiv preprint, RSS, NeurIPS 등. Venue 정보가 있으면 반드시 명시, 없으면 "arXiv preprint"으로 표기)
   - **출판 시기** (날짜 또는 연도. 반드시 포함)
   - 한줄 요약
3. **뉴스 목록** (있는 경우, 출처와 날짜 포함)
4. **연구 트렌드 메모** (이 분야에서 눈에 띄는 동향 1-2줄)

중요: 각 논문마다 학회/출판처와 출판 시기는 빠지면 안 됩니다.
형식은 GitHub Markdown으로 작성하세요.
COACH 프로젝트(Hamiltonian mechanics 기반 VLA correction head)와 관련성이 높은 논문은 ⭐로 표시해주세요.
"""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"]
    except Exception as e:
        print(f"[Claude API] Failed: {e}")
        return _fallback_format(papers)


def _fallback_format(papers: list[dict]) -> str:
    """Claude API 실패 시 기본 포맷."""
    lines = ["## 수집된 항목\n"]
    for p in papers:
        lines.append(f"### [{p['title']}]({p['url']})")
        venue = p.get('venue', '')
        lines.append(f"- **출처**: {p['source']} | **학회**: {venue or 'N/A'} | **날짜**: {p['date']}")
        if p["authors"]:
            lines.append(f"- **저자**: {p['authors']}")
        if p["abstract"]:
            lines.append(f"- {p['abstract'][:200]}...")
        lines.append("")
    return "\n".join(lines)


# ── GitHub Issue 생성 ─────────────────────────────────
def create_github_issue(title: str, body: str) -> Optional[str]:
    """GitHub API로 Issue 생성."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # owner/repo 형식
    if not token or not repo:
        print("[GitHub] GITHUB_TOKEN or GITHUB_REPOSITORY not set")
        return None

    url = f"https://api.github.com/repos/{repo}/issues"
    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": ["daily-digest", "vla", "physical-ai"],
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        issue_url = data.get("html_url", "")
        print(f"[GitHub] Issue created: {issue_url}")
        return issue_url
    except Exception as e:
        print(f"[GitHub] Failed to create issue: {e}")
        return None


# ── 중복 제거 ─────────────────────────────────────────
def deduplicate(papers: list[dict]) -> list[dict]:
    """제목 유사도 기반 중복 제거."""
    seen = set()
    unique = []
    for p in papers:
        # 소문자 + 특수문자 제거로 정규화
        normalized = re.sub(r"[^a-z0-9]", "", p["title"].lower())
        if normalized not in seen:
            seen.add(normalized)
            unique.append(p)
    return unique


# ── 메인 ──────────────────────────────────────────────
def main():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    print(f"=== VLA/Physical AI Daily Digest — {today} ===\n")

    # 1. 수집
    print("📡 Collecting from arXiv...")
    arxiv_papers = search_arxiv()
    print(f"   → {len(arxiv_papers)} papers")

    print("📡 Collecting from Semantic Scholar...")
    semantic_papers = search_semantic_scholar()
    print(f"   → {len(semantic_papers)} papers")

    print("📡 Collecting from Google News...")
    news_articles = search_google_news()
    print(f"   → {len(news_articles)} articles")

    print("📡 Collecting from Google Scholar...")
    scholar_papers = search_google_scholar()
    print(f"   → {len(scholar_papers)} papers")

    # 2. 합치기 + 중복 제거
    all_items = arxiv_papers + semantic_papers + scholar_papers + news_articles
    all_items = deduplicate(all_items)
    print(f"\n📊 Total unique items: {len(all_items)}")

    if not all_items:
        print("No items found. Skipping issue creation.")
        return

    # 3. Claude API 요약
    print("\n🤖 Summarizing with Claude...")
    digest_body = summarize_with_claude(all_items)

    # 4. GitHub Issue 생성
    issue_title = f"📄 VLA/Physical AI Daily Digest — {today}"
    full_body = f"""# VLA / Physical AI Daily Digest
> 자동 생성: {today} 10:00 KST

{digest_body}

---
<details>
<summary>📊 수집 통계</summary>

| 소스 | 수집 수 |
|------|---------|
| arXiv | {len(arxiv_papers)} |
| Semantic Scholar | {len(semantic_papers)} |
| Google Scholar | {len(scholar_papers)} |
| Google News | {len(news_articles)} |
| **총 (중복 제거 후)** | **{len(all_items)}** |

</details>

---
*🤖 Generated by [VLA Paper Digest](https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'your/repo')}) — Claude API + GitHub Actions*
"""

    print("\n📤 Creating GitHub Issue...")
    issue_url = create_github_issue(issue_title, full_body)

    if issue_url:
        print(f"\n✅ Done! Issue: {issue_url}")
    else:
        # Issue 생성 실패 시 stdout으로 출력
        print("\n⚠️ Could not create issue. Digest content:")
        print(full_body)


if __name__ == "__main__":
    main()