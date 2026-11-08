from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def fetch(url, limit=6_000_000):
    request = urllib.request.Request(url, headers={"User-Agent": "LUMEN-Science/0.1 (local research workbench)",
                                                   "Accept": "application/json, application/xml"})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("检索结果超过读取上限")
        return raw


def crossref(query, limit=8):
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode({
        "query.bibliographic": query, "rows": limit})
    payload = json.loads(fetch(url))
    records = []
    for item in payload.get("message", {}).get("items", []):
        parts = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])
        doi = item.get("DOI", "")
        records.append({"doi": doi, "title": (item.get("title") or ["未提供标题"])[0],
                        "authors": [(" ".join([a.get("given", ""), a.get("family", "")])).strip()
                                    for a in item.get("author", [])[:20]],
                        "year": parts[0][0] if parts and parts[0] else None,
                        "journal": (item.get("container-title") or [""])[0],
                        "url": "https://doi.org/" + urllib.parse.quote(doi, safe="/"),
                        "source": "Crossref", "retrieved": datetime.now(timezone.utc).isoformat(),
                        "abstract": re.sub("<[^>]+>", "", item.get("abstract", ""))[:6000]})
    return records


def pubmed(query, limit=8):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search = json.loads(fetch(base + "esearch.fcgi?" + urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": limit, "retmode": "json"})))
    ids = search.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    root = ET.fromstring(fetch(base + "efetch.fcgi?" + urllib.parse.urlencode({
        "db": "pubmed", "id": ",".join(ids), "retmode": "xml"})))
    records = []
    for article in root.findall(".//PubmedArticle"):
        title = article.find(".//ArticleTitle")
        pmid = article.findtext(".//PMID", "")
        doi = next((x.text for x in article.findall(".//ArticleId") if x.attrib.get("IdType") == "doi"), "")
        records.append({"doi": doi or "PMID:" + pmid,
                        "title": "".join(title.itertext()) if title is not None else "未提供标题",
                        "authors": [" ".join([a.findtext("ForeName", ""), a.findtext("LastName", "")]).strip()
                                    for a in article.findall(".//Author")[:20]],
                        "year": article.findtext(".//JournalIssue/PubDate/Year"),
                        "journal": article.findtext(".//Journal/Title", ""),
                        "url": "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/",
                        "source": "PubMed", "retrieved": datetime.now(timezone.utc).isoformat(),
                        "abstract": "\n".join("".join(x.itertext()) for x in article.findall(".//AbstractText"))[:6000]})
    return records


def search(query, source="crossref", limit=8):
    query = str(query).strip()
    if not query or len(query) > 500:
        raise ValueError("请输入 1–500 字符的检索词")
    limit = max(1, min(int(limit), 20))
    return crossref(query, limit) if source == "crossref" else pubmed(query, limit) if source == "pubmed" else []


def bibtex(records):
    def clean(value):
        return str(value or "").replace("\\", "\\textbackslash ").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
    result = []
    for i, record in enumerate(records):
        fields = {"title": record["title"], "author": " and ".join(record.get("authors", [])),
                  "journal": record.get("journal"), "year": record.get("year"),
                  "doi": record.get("doi") if not record.get("doi", "").startswith("PMID:") else "",
                  "url": record.get("url")}
        result.append("@article{lumen" + str(i + 1) + ",\n" +
                      ",\n".join("  " + k + " = {" + clean(v) + "}" for k, v in fields.items() if v) + "\n}")
    return "\n\n".join(result)
