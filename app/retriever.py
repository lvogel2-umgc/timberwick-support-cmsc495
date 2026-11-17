"""
Author: Belqis Wahidi

KnowledgeRetriever: finds approved help articles that match a customer question.

Each article is indexed by its title and its example questions. A question is turned into a
TF-IDF vector and compared to every indexed phrase with cosine similarity. An article's
relevance score is its best-matching phrase. Only approved articles are ever returned, and an
empty list is returned when nothing matches, so the AI never makes up an answer.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class Article:
    article_id: str
    title: str
    body: str
    questions: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeMatch:
    article_id: str
    title: str
    excerpt: str
    relevance_score: float


class KnowledgeRetriever:
    """Searches the approved knowledge base with a scikit-learn TF-IDF model."""

    def __init__(self, articles: list[Article], min_score: float = 0.1) -> None:
        if not articles:
            raise ValueError("The knowledge base must contain at least one article.")
        self._articles = {article.article_id: article for article in articles}
        self._min_score = min_score

        # One row per indexed phrase, remembering which article each row belongs to.
        phrases: list[str] = []
        self._row_article_ids: list[str] = []
        for article in articles:
            for phrase in (article.title, *article.questions):
                phrases.append(phrase)
                self._row_article_ids.append(article.article_id)

        self._vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"(?u)\b\w+\b",
        )
        self._matrix = self._vectorizer.fit_transform(phrases)

    @classmethod
    def from_json(cls, path: str | Path) -> "KnowledgeRetriever":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        articles = [
            Article(
                article_id=item["article_id"],
                title=item["title"],
                body=item["body"],
                questions=tuple(item.get("questions", [])),
            )
            for item in data["articles"]
        ]
        return cls(articles)

    def get_article(self, article_id: str) -> Article | None:
        return self._articles.get(article_id)

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeMatch]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        query_vector = self._vectorizer.transform([query])
        if query_vector.nnz == 0:
            # None of the words in the question appear in the knowledge base.
            return []

        scores = cosine_similarity(query_vector, self._matrix)[0]
        best_by_article: dict[str, float] = {}
        for article_id, score in zip(self._row_article_ids, scores, strict=True):
            if score > best_by_article.get(article_id, 0.0):
                best_by_article[article_id] = float(score)

        ranked = sorted(best_by_article.items(), key=lambda item: item[1], reverse=True)
        matches = []
        for article_id, score in ranked[:top_k]:
            if score < self._min_score:
                break
            article = self._articles[article_id]
            matches.append(
                KnowledgeMatch(
                    article_id=article_id,
                    title=article.title,
                    excerpt=article.body[:200],
                    relevance_score=round(min(score, 1.0), 4),
                )
            )
        return matches
