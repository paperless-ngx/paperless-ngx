from __future__ import annotations

import hmac
import logging
import pickle
import re
import warnings
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from datetime import datetime
    from types import TracebackType
    from typing import BinaryIO
    from typing import Self

    from numpy import ndarray
    from sklearn.neural_network import MLPClassifier

from django.conf import settings
from django.core.cache import cache
from django.core.cache import caches
from django.db.models import Prefetch

from documents.caching import CACHE_5_MINUTES
from documents.caching import CACHE_50_MINUTES
from documents.caching import CLASSIFIER_HASH_KEY
from documents.caching import CLASSIFIER_MODIFIED_KEY
from documents.caching import CLASSIFIER_VERSION_KEY
from documents.caching import StoredLRUCache
from documents.models import Document
from documents.models import MatchingModel
from documents.models import Tag
from paperless.signed_pickle import SignedPickleError
from paperless.signed_pickle import signed_pickle_dumps
from paperless.signed_pickle import signed_pickle_loads

logger = logging.getLogger("paperless.classifier")


def _predict_with_threshold(classifier, X, threshold: float) -> int | None:
    """
    Return the predicted class id, or None if:
    - the prediction is -1 (no match), or
    - the winning class probability is below the configured threshold.

    Using predict_proba() instead of predict() lets us apply a minimum-confidence
    cutoff so that uncertain predictions are discarded rather than assigned.
    """
    probas = classifier.predict_proba(X)[0]
    best_idx = int(probas.argmax())
    best_class = int(classifier.classes_[best_idx])

    if best_class == -1:
        return None
    if threshold > 0.0 and probas[best_idx] < threshold:
        return None
    return best_class


ADVANCED_TEXT_PROCESSING_ENABLED = (
    settings.NLTK_LANGUAGE is not None and settings.NLTK_ENABLED
)

read_cache = caches["read-cache"]


RE_DIGIT = re.compile(r"\d")
RE_WORD = re.compile(r"\b[\w]+\b")  # words that may contain digits

# Documents whose content is fetched per query while training
_CONTENT_CHUNK_SIZE = 1000


class _SignedFileWriter:
    """
    Atomically writes a file made of an HMAC signature followed by the data,
    signing the data as it streams to disk rather than holding it in memory.

    The signature is only known once everything is written, so its space is
    reserved at the start of the file and filled in on exit. The target is only
    replaced once the file is complete; on error the partial file is removed.
    """

    def __init__(self, target: Path, mac: hmac.HMAC) -> None:
        self._target = target
        self._temp = target.with_name(f"{target.name}.part")
        self._mac = mac
        self._file: BinaryIO

    def __enter__(self) -> Self:
        self._file = self._temp.open("wb")
        self._file.write(bytes(self._mac.digest_size))
        return self

    def write(self, data: bytes | memoryview) -> int:
        self._mac.update(data)
        return self._file.write(data)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            with self._file:
                if exc_type is None:
                    self._file.seek(0)
                    self._file.write(self._mac.digest())
            if exc_type is None:
                self._temp.rename(self._target)
        finally:
            # A no-op after a successful rename, otherwise removes the partial file
            self._temp.unlink(missing_ok=True)


class IncompatibleClassifierVersionError(Exception):
    def __init__(self, message: str, *args: object) -> None:
        self.message: str = message
        super().__init__(*args)


class ClassifierModelCorruptError(Exception):
    pass


def load_classifier(*, raise_exception: bool = False) -> DocumentClassifier | None:
    if not settings.MODEL_FILE.is_file():
        logger.debug(
            "Document classification model does not exist (yet), not "
            "performing automatic matching.",
        )
        return None

    classifier = DocumentClassifier()
    try:
        classifier.load()

    except IncompatibleClassifierVersionError as e:
        logger.info(f"Classifier version incompatible: {e.message}, will re-train")
        Path(settings.MODEL_FILE).unlink()
        classifier = None
        if raise_exception:
            raise e
    except ClassifierModelCorruptError as e:
        # there's something wrong with the model file.
        logger.exception(
            "Unrecoverable error while loading document "
            "classification model, deleting model file.",
        )
        Path(settings.MODEL_FILE).unlink()
        classifier = None
        if raise_exception:
            raise e
    except OSError as e:
        logger.exception("IO error while loading document classification model")
        classifier = None
        if raise_exception:
            raise e
    except Exception as e:  # pragma: no cover
        logger.exception("Unknown error while loading document classification model")
        classifier = None
        if raise_exception:
            raise e

    return classifier


class DocumentClassifier:
    # v7 - Updated scikit-learn package version
    # v8 - Added storage path classifier
    # v9 - Changed from hashing to time/ids for re-train check
    # v10 - HMAC-signed model file
    # v11 - Use sample_weight for balanced training; predict_proba with threshold;
    #       drop training-only MLP state before saving
    FORMAT_VERSION = 11

    HMAC_SIZE = 32  # SHA-256 digest length

    def __init__(self) -> None:
        # last time a document changed and therefore training might be required
        self.last_doc_change_time: datetime | None = None
        # Hash of primary keys of AUTO matching values last used in training
        self.last_auto_type_hash: bytes | None = None

        self.data_vectorizer = None
        self.data_vectorizer_hash = None
        self.tags_binarizer = None
        self.tags_classifier = None
        self.correspondent_classifier = None
        self.document_type_classifier = None
        self.storage_path_classifier = None
        self._stemmer = None
        # 10,000 elements roughly use 200 to 500 KB per worker,
        # and also in the shared Redis cache,
        # Keep this cache small to minimize lookup and I/O latency.
        if ADVANCED_TEXT_PROCESSING_ENABLED:
            self._stem_cache = StoredLRUCache(
                f"stem_cache_v{self.FORMAT_VERSION}",
                capacity=10000,
            )
        self._stop_words = None

    def _update_data_vectorizer_hash(self) -> None:
        self.data_vectorizer_hash = sha256(
            pickle.dumps(self.data_vectorizer),
        ).hexdigest()

    @staticmethod
    def _new_hmac() -> hmac.HMAC:
        return hmac.new(settings.SECRET_KEY.encode(), digestmod=sha256)

    @staticmethod
    def _strip_training_state(classifier: MLPClassifier) -> None:
        """
        Drop MLPClassifier state which is only used during fit(), never by predict().

        The Adam optimizer keeps two moment arrays the size of the weights, and
        without early_stopping _best_coefs/_best_intercepts are just a copy of the
        initial random weights. Together that is 3x the size of the weights, which
        would otherwise be pickled and loaded along with the model.
        """
        del classifier._optimizer
        del classifier._best_coefs
        del classifier._best_intercepts

    @staticmethod
    def _compute_hmac(data: bytes | memoryview) -> bytes:
        mac = DocumentClassifier._new_hmac()
        mac.update(data)
        return mac.digest()

    def load(self) -> None:
        from sklearn.exceptions import InconsistentVersionWarning

        raw = Path(settings.MODEL_FILE).read_bytes()

        if len(raw) <= self.HMAC_SIZE:
            raise ClassifierModelCorruptError

        # Slice through a memoryview so the (potentially multi-GB) payload is
        # not copied; hmac and pickle both accept buffers directly.
        # The whole file is still verified from memory before unpickling, rather
        # than streamed from disk, so it cannot change between check and load.
        view = memoryview(raw)
        signature = view[: self.HMAC_SIZE]
        data = view[self.HMAC_SIZE :]

        if not hmac.compare_digest(signature, self._compute_hmac(data)):
            raise ClassifierModelCorruptError

        # Catch warnings for processing
        with warnings.catch_warnings(record=True) as w:
            try:
                (
                    schema_version,
                    self.last_doc_change_time,
                    self.last_auto_type_hash,
                    self.data_vectorizer,
                    self.tags_binarizer,
                    self.tags_classifier,
                    self.correspondent_classifier,
                    self.document_type_classifier,
                    self.storage_path_classifier,
                ) = pickle.loads(data)
            except Exception as err:
                raise ClassifierModelCorruptError from err

        if schema_version != self.FORMAT_VERSION:
            raise IncompatibleClassifierVersionError(
                "Cannot load classifier, incompatible versions.",
            )

        self._update_data_vectorizer_hash()

        # Check for the warning about unpickling from differing versions
        # and consider it incompatible
        sk_learn_warning_url = (
            "https://scikit-learn.org/stable/"
            "model_persistence.html"
            "#security-maintainability-limitations"
        )
        for warning in w:
            # The warning is inconsistent, the MLPClassifier is a specific warning, others have not updated yet
            if issubclass(warning.category, InconsistentVersionWarning) or (
                issubclass(warning.category, UserWarning)
                and sk_learn_warning_url in str(warning.message)
            ):
                raise IncompatibleClassifierVersionError("sklearn version update")

    def save(self) -> None:
        # Stream to disk instead of building the payload in memory. Protocol 5+
        # pickles numpy arrays without copying them (the default is 4 before 3.14).
        with _SignedFileWriter(settings.MODEL_FILE, self._new_hmac()) as f:
            pickle.dump(
                (
                    self.FORMAT_VERSION,
                    self.last_doc_change_time,
                    self.last_auto_type_hash,
                    self.data_vectorizer,
                    self.tags_binarizer,
                    self.tags_classifier,
                    self.correspondent_classifier,
                    self.document_type_classifier,
                    self.storage_path_classifier,
                ),
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    def train(
        self,
        status_callback: Callable[[str], None] | None = None,
    ) -> bool:
        notify = status_callback if status_callback is not None else lambda _: None

        # Get non-inbox documents
        docs_queryset = Document.objects.exclude(
            tags__is_inbox_tag=True,
        ).order_by("pk")

        # No documents exit to train against
        doc_count = docs_queryset.count()
        if doc_count == 0:
            raise ValueError("No training data available.")

        labels_tags = []
        labels_correspondent = []
        labels_document_type = []
        labels_storage_path = []
        # Content is fetched separately later, for exactly these documents in this
        # order, so it never all has to be in memory at once
        doc_pks: list[int] = []
        latest_doc_change: datetime | None = None

        # Step 1: Extract and preprocess training data from the database.
        logger.debug("Gathering data from database...")
        notify(f"Gathering data from {doc_count} document(s)...")
        hasher = sha256()
        for doc in (
            docs_queryset.defer("content")
            .select_related("document_type", "correspondent", "storage_path")
            .prefetch_related(
                Prefetch(
                    "tags",
                    queryset=Tag.objects.filter(
                        matching_algorithm=MatchingModel.MATCH_AUTO,
                    )
                    .order_by("pk")
                    .only("pk"),
                    to_attr="auto_tags",
                ),
            )
            .iterator(chunk_size=2000)
        ):
            doc_pks.append(doc.pk)
            if latest_doc_change is None or doc.modified > latest_doc_change:
                latest_doc_change = doc.modified

            y = -1
            dt = doc.document_type
            if dt and dt.matching_algorithm == MatchingModel.MATCH_AUTO:
                y = dt.pk
            hasher.update(y.to_bytes(4, "little", signed=True))
            labels_document_type.append(y)

            y = -1
            cor = doc.correspondent
            if cor and cor.matching_algorithm == MatchingModel.MATCH_AUTO:
                y = cor.pk
            hasher.update(y.to_bytes(4, "little", signed=True))
            labels_correspondent.append(y)

            tags: list[int] = [tag.pk for tag in doc.auto_tags]
            for tag in tags:
                hasher.update(tag.to_bytes(4, "little", signed=True))
            labels_tags.append(tags)

            y = -1
            sp = doc.storage_path
            if sp and sp.matching_algorithm == MatchingModel.MATCH_AUTO:
                y = sp.pk
            hasher.update(y.to_bytes(4, "little", signed=True))
            labels_storage_path.append(y)

        labels_tags_unique = {tag for tags in labels_tags for tag in tags}

        num_tags = len(labels_tags_unique)

        # Check if retraining is actually required.
        # A document has been updated since the classifier was trained
        # New auto tags, types, correspondent, storage paths exist
        if (
            self.last_doc_change_time is not None
            and self.last_doc_change_time >= latest_doc_change
        ) and self.last_auto_type_hash == hasher.digest():
            logger.info("No updates since last training")
            # Set the classifier information into the cache
            # Caching for 50 minutes, so slightly less than the normal retrain time
            cache.set(
                CLASSIFIER_MODIFIED_KEY,
                self.last_doc_change_time,
                CACHE_50_MINUTES,
            )
            cache.set(CLASSIFIER_HASH_KEY, hasher.hexdigest(), CACHE_50_MINUTES)
            cache.set(CLASSIFIER_VERSION_KEY, self.FORMAT_VERSION, CACHE_50_MINUTES)
            return False

        # subtract 1 since -1 (null) is also part of the classes.

        # union with {-1} accounts for cases where all documents have
        # correspondents and types assigned, so -1 isn't part of labels_x, which
        # it usually is.
        num_correspondents: int = len(set(labels_correspondent) | {-1}) - 1
        num_document_types: int = len(set(labels_document_type) | {-1}) - 1
        num_storage_paths: int = len(set(labels_storage_path) | {-1}) - 1

        logger.debug(
            f"{len(doc_pks)} documents, {num_tags} tag(s), {num_correspondents} correspondent(s), "
            f"{num_document_types} document type(s). {num_storage_paths} storage path(s)",
        )

        from sklearn.feature_extraction.text import CountVectorizer
        from sklearn.neural_network import MLPClassifier
        from sklearn.preprocessing import LabelBinarizer
        from sklearn.preprocessing import MultiLabelBinarizer

        # MLPClassifier does not support class_weight directly
        # (https://github.com/scikit-learn/scikit-learn/issues/9113), so we use
        # compute_sample_weight to balance classes during training and prevent
        # over-represented correspondents from dominating predictions.
        # https://scikit-learn.org/stable/modules/generated/sklearn.utils.class_weight.compute_sample_weight.html
        from sklearn.utils.class_weight import compute_sample_weight

        # Step 2: vectorize data
        logger.debug("Vectorizing data...")
        notify("Vectorizing document content...")

        def content_generator() -> Iterator[str]:
            """
            Generates the content for documents, in the same order as the labels,
            fetching it a chunk at a time
            """
            for start in range(0, len(doc_pks), _CONTENT_CHUNK_SIZE):
                chunk = doc_pks[start : start + _CONTENT_CHUNK_SIZE]
                docs = Document.objects.only("content").order_by().in_bulk(chunk)
                for pk in chunk:
                    # A document deleted since its labels were gathered still
                    # needs a row, so labels and content stay aligned
                    doc = docs.get(pk)
                    yield self.preprocess_content(
                        doc.content if doc is not None else "",
                        shared_cache=False,
                    )

        self.data_vectorizer = CountVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=0.01,
        )

        data_vectorized: ndarray = self.data_vectorizer.fit_transform(
            content_generator(),
        )

        # See the notes here:
        # https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.CountVectorizer.html
        # This attribute isn't needed to function and can be large
        self.data_vectorizer.stop_words_ = None

        # Step 3: train the classifiers
        if num_tags > 0:
            logger.debug("Training tags classifier...")
            notify(f"Training tags classifier ({num_tags} tag(s))...")

            if num_tags == 1:
                # Special case where only one tag has auto:
                # Fallback to binary classification.
                labels_tags = [
                    label[0] if len(label) == 1 else -1 for label in labels_tags
                ]
                self.tags_binarizer = LabelBinarizer()
                labels_tags_vectorized: ndarray = self.tags_binarizer.fit_transform(
                    labels_tags,
                ).ravel()
            else:
                self.tags_binarizer = MultiLabelBinarizer()
                labels_tags_vectorized = self.tags_binarizer.fit_transform(labels_tags)

            self.tags_classifier = MLPClassifier(tol=0.01, random_state=0)
            self.tags_classifier.fit(data_vectorized, labels_tags_vectorized)
            self._strip_training_state(self.tags_classifier)
        else:
            self.tags_classifier = None
            logger.debug("There are no tags. Not training tags classifier.")

        if num_correspondents > 0:
            logger.debug("Training correspondent classifier...")
            notify(
                f"Training correspondent classifier ({num_correspondents} correspondent(s))...",
            )
            self.correspondent_classifier = MLPClassifier(tol=0.01, random_state=0)
            self.correspondent_classifier.fit(
                data_vectorized,
                labels_correspondent,
                sample_weight=compute_sample_weight("balanced", labels_correspondent),
            )
            self._strip_training_state(self.correspondent_classifier)
        else:
            self.correspondent_classifier = None
            logger.debug(
                "There are no correspondents. Not training correspondent classifier.",
            )

        if num_document_types > 0:
            logger.debug("Training document type classifier...")
            notify(
                f"Training document type classifier ({num_document_types} type(s))...",
            )
            self.document_type_classifier = MLPClassifier(tol=0.01, random_state=0)
            self.document_type_classifier.fit(
                data_vectorized,
                labels_document_type,
                sample_weight=compute_sample_weight("balanced", labels_document_type),
            )
            self._strip_training_state(self.document_type_classifier)
        else:
            self.document_type_classifier = None
            logger.debug(
                "There are no document types. Not training document type classifier.",
            )

        if num_storage_paths > 0:
            logger.debug(
                "Training storage paths classifier...",
            )
            notify(f"Training storage path classifier ({num_storage_paths} path(s))...")
            self.storage_path_classifier = MLPClassifier(tol=0.01, random_state=0)
            self.storage_path_classifier.fit(
                data_vectorized,
                labels_storage_path,
                sample_weight=compute_sample_weight("balanced", labels_storage_path),
            )
            self._strip_training_state(self.storage_path_classifier)
        else:
            self.storage_path_classifier = None
            logger.debug(
                "There are no storage paths. Not training storage path classifier.",
            )

        self.last_doc_change_time = latest_doc_change
        self.last_auto_type_hash = hasher.digest()
        self._update_data_vectorizer_hash()

        # Set the classifier information into the cache
        # Caching for 50 minutes, so slightly less than the normal retrain time
        cache.set(CLASSIFIER_MODIFIED_KEY, self.last_doc_change_time, CACHE_50_MINUTES)
        cache.set(CLASSIFIER_HASH_KEY, hasher.hexdigest(), CACHE_50_MINUTES)
        cache.set(CLASSIFIER_VERSION_KEY, self.FORMAT_VERSION, CACHE_50_MINUTES)

        return True

    def _init_advanced_text_processing(self):
        if self._stop_words is None or self._stemmer is None:
            import nltk
            from nltk.corpus import stopwords
            from nltk.stem import SnowballStemmer

            # Not really hacky, since it isn't private and is documented, but
            # set the search path for NLTK data to the single location it should be in
            nltk.data.path = [settings.NLTK_DIR]
            try:
                # Preload the corpus early, to force the lazy loader to transform
                stopwords.ensure_loaded()

                # Do some one time setup
                # Sometimes, somehow, there's multiple threads loading the corpus
                # and it's not thread safe, raising an AttributeError
                self._stemmer = SnowballStemmer(settings.NLTK_LANGUAGE)
                self._stop_words = frozenset(stopwords.words(settings.NLTK_LANGUAGE))
            except AttributeError:
                logger.debug("Could not initialize NLTK for advanced text processing.")
                return False
        return True

    def stem_and_skip_stop_words(self, words: list[str], *, shared_cache=True):
        """
        Reduce a list of words to their stem. Stop words are converted to empty strings.
        :param words: the list of words to stem
        """

        def _stem_and_skip_stop_word(word: str):
            """
            Reduce a given word to its stem. If it's a stop word, return an empty string.
            E.g. "amazement", "amaze" and "amazed" all return "amaz".
            """
            cached = self._stem_cache.get(word)
            if cached is not None:
                return cached
            elif word in self._stop_words:
                return ""
            # Assumption: words that contain numbers are never stemmed
            elif RE_DIGIT.search(word):
                return word
            else:
                result = self._stemmer.stem(word)
                self._stem_cache.set(word, result)
                return result

        if shared_cache:
            self._stem_cache.load()

        # Stem the words and skip stop words
        result = " ".join(
            filter(None, (_stem_and_skip_stop_word(w) for w in words)),
        )
        if shared_cache:
            self._stem_cache.save()
        return result

    def preprocess_content(
        self,
        content: str,
        *,
        shared_cache=True,
    ) -> str:
        """
        Process the contents of a document, distilling it down into
        words which are meaningful to the content.

        A stemmer cache is shared across workers with the parameter "shared_cache".
        This is unnecessary when training the classifier.
        """

        # Lower case the document, reduce space,
        # and keep only letters and digits.
        content = " ".join(match.group().lower() for match in RE_WORD.finditer(content))

        if ADVANCED_TEXT_PROCESSING_ENABLED:
            from nltk.tokenize import word_tokenize

            if not self._init_advanced_text_processing():
                return content
            # Tokenize
            # This splits the content into tokens, roughly words
            words = word_tokenize(content, language=settings.NLTK_LANGUAGE)
            # Stem the words and skip stop words
            content = self.stem_and_skip_stop_words(words, shared_cache=shared_cache)

        return content

    def _get_vectorizer_cache_key(self, content: str):
        hash = sha256(content.encode())
        hash.update(
            f"|{self.FORMAT_VERSION}|{settings.NLTK_LANGUAGE}|{settings.NLTK_ENABLED}|{self.data_vectorizer_hash}".encode(),
        )
        return f"vectorized_content_{hash.hexdigest()}"

    def _vectorize(self, content: str):
        key = self._get_vectorizer_cache_key(content)
        serialized_result = read_cache.get(key)
        if serialized_result is None:
            result = self.data_vectorizer.transform([self.preprocess_content(content)])
            read_cache.set(key, signed_pickle_dumps(result), CACHE_5_MINUTES)
        else:
            try:
                result = signed_pickle_loads(serialized_result)
            except SignedPickleError:
                result = self.data_vectorizer.transform(
                    [self.preprocess_content(content)],
                )
                read_cache.set(key, signed_pickle_dumps(result), CACHE_5_MINUTES)
            else:
                read_cache.touch(key, CACHE_5_MINUTES)
        return result

    def predict_correspondent(self, content: str) -> int | None:
        if self.correspondent_classifier:
            X = self._vectorize(content)
            predicted_id = _predict_with_threshold(
                self.correspondent_classifier,
                X,
                settings.CLASSIFIER_MATCH_THRESHOLD,
            )
            return predicted_id
        return None

    def predict_document_type(self, content: str) -> int | None:
        if self.document_type_classifier:
            X = self._vectorize(content)
            predicted_id = _predict_with_threshold(
                self.document_type_classifier,
                X,
                settings.CLASSIFIER_MATCH_THRESHOLD,
            )
            return predicted_id
        return None

    def predict_tags(self, content: str) -> list[int]:
        from sklearn.utils.multiclass import type_of_target

        if self.tags_classifier:
            X = self._vectorize(content)
            y = self.tags_classifier.predict(X)
            tags_ids = self.tags_binarizer.inverse_transform(y)[0]
            if type_of_target(y).startswith("multilabel"):
                # the usual case when there are multiple tags.
                return list(tags_ids)
            elif type_of_target(y) == "binary" and tags_ids != -1:
                # This is for when we have binary classification with only one
                # tag and the result is to assign this tag.
                return [tags_ids]
            else:
                # Usually binary as well with -1 as the result, but we're
                # going to catch everything else here as well.
                return []
        else:
            return []

    def predict_storage_path(self, content: str) -> int | None:
        if self.storage_path_classifier:
            X = self._vectorize(content)
            predicted_id = _predict_with_threshold(
                self.storage_path_classifier,
                X,
                settings.CLASSIFIER_MATCH_THRESHOLD,
            )
            return predicted_id
        return None
