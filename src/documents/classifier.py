import logging
import os
import pickle

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import MultiLabelBinarizer, LabelBinarizer

from documents.models import Correspondent, DocumentType, Tag, Document
from paperless import settings


def preprocess_content(content):
    content = content.lower()
    content = content.strip()
    content = content.replace("\n", " ")
    content = content.replace("\r", " ")
    while content.find("  ") > -1:
        content = content.replace("  ", " ")
    return content


class DocumentClassifier(object):

    def __init__(self):
        self.classifier_version = 0

        self.data_vectorizer = None

        self.tags_binarizer = None
        self.correspondent_binarizer = None
        self.document_type_binarizer = None

        self.tags_classifier = None
        self.correspondent_classifier = None
        self.document_type_classifier = None

    def reload(self):
        if os.path.getmtime(settings.MODEL_FILE) > self.classifier_version:
            logging.getLogger(__name__).info("Reloading classifier models")
            with open(settings.MODEL_FILE, "rb") as f:
                self.data_vectorizer = pickle.load(f)
                self.tags_binarizer = pickle.load(f)
                self.correspondent_binarizer = pickle.load(f)
                self.document_type_binarizer = pickle.load(f)

                self.tags_classifier = pickle.load(f)
                self.correspondent_classifier = pickle.load(f)
                self.document_type_classifier = pickle.load(f)
            self.classifier_version = os.path.getmtime(settings.MODEL_FILE)

    def save_classifier(self):
        with open(settings.MODEL_FILE, "wb") as f:
            pickle.dump(self.data_vectorizer, f)

            pickle.dump(self.tags_binarizer, f)
            pickle.dump(self.correspondent_binarizer, f)
            pickle.dump(self.document_type_binarizer, f)

            pickle.dump(self.tags_classifier, f)
            pickle.dump(self.correspondent_classifier, f)
            pickle.dump(self.document_type_classifier, f)

    def train(self):
        data = list()
        labels_tags = list()
        labels_correspondent = list()
        labels_document_type = list()

        # Step 1: Extract and preprocess training data from the database.
        logging.getLogger(__name__).info("Gathering data from database...")
        for doc in Document.objects.exclude(tags__is_inbox_tag=True):
            data.append(preprocess_content(doc.content))

            y = -1
            if doc.document_type:
                if doc.document_type.automatic_classification:
                    y = doc.document_type.id
            labels_document_type.append(y)

            y = -1
            if doc.correspondent:
                if doc.correspondent.automatic_classification:
                    y = doc.correspondent.id
            labels_correspondent.append(y)

            tags = [tag.id for tag in doc.tags.filter(
                automatic_classification=True
            )]
            labels_tags.append(tags)

        labels_tags_unique = set([tag for tags in labels_tags for tag in tags])
        logging.getLogger(__name__).info(
            "{} documents, {} tag(s), {} correspondent(s), "
            "{} document type(s).".format(
                len(data),
                len(labels_tags_unique),
                len(set(labels_correspondent)),
                len(set(labels_document_type))
            )
        )

        # Step 2: vectorize data
        logging.getLogger(__name__).info("Vectorizing data...")
        self.data_vectorizer = CountVectorizer(
            analyzer="char",
            ngram_range=(3, 5),
            min_df=0.1
        )
        data_vectorized = self.data_vectorizer.fit_transform(data)

        self.tags_binarizer = MultiLabelBinarizer()
        labels_tags_vectorized = self.tags_binarizer.fit_transform(labels_tags)

        self.correspondent_binarizer = LabelBinarizer()
        labels_correspondent_vectorized = \
            self.correspondent_binarizer.fit_transform(labels_correspondent)

        self.document_type_binarizer = LabelBinarizer()
        labels_document_type_vectorized = \
            self.document_type_binarizer.fit_transform(labels_document_type)

        # Step 3: train the classifiers
        if len(self.tags_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training tags classifier...")
            self.tags_classifier = MLPClassifier(verbose=True)
            self.tags_classifier.fit(data_vectorized, labels_tags_vectorized)
        else:
            self.tags_classifier = None
            logging.getLogger(__name__).info(
                "There are no tags. Not training tags classifier."
            )

        if len(self.correspondent_binarizer.classes_) > 0:
            logging.getLogger(__name__).info(
                "Training correspondent classifier..."
            )
            self.correspondent_classifier = MLPClassifier(verbose=True)
            self.correspondent_classifier.fit(
                data_vectorized,
                labels_correspondent_vectorized
            )
        else:
            self.correspondent_classifier = None
            logging.getLogger(__name__).info(
                "There are no correspondents. Not training correspondent "
                "classifier."
            )

        if len(self.document_type_binarizer.classes_) > 0:
            logging.getLogger(__name__).info(
                "Training document type classifier..."
            )
            self.document_type_classifier = MLPClassifier(verbose=True)
            self.document_type_classifier.fit(
                data_vectorized,
                labels_document_type_vectorized
            )
        else:
            self.document_type_classifier = None
            logging.getLogger(__name__).info(
                "There are no document types. Not training document type "
                "classifier."
            )

    def classify_document(
            self, document, classify_correspondent=False,
            classify_document_type=False, classify_tags=False,
            replace_tags=False):

        X = self.data_vectorizer.transform(
            [preprocess_content(document.content)]
        )

        if classify_correspondent and self.correspondent_classifier:
            self._classify_correspondent(X, document)

        if classify_document_type and self.document_type_classifier:
            self._classify_document_type(X, document)

        if classify_tags and self.tags_classifier:
            self._classify_tags(X, document, replace_tags)

        document.save(update_fields=("correspondent", "document_type"))

    def _classify_correspondent(self, X, document):
        y = self.correspondent_classifier.predict(X)
        correspondent_id = self.correspondent_binarizer.inverse_transform(y)[0]
        try:
            correspondent = None
            if correspondent_id != -1:
                correspondent = Correspondent.objects.get(id=correspondent_id)
                logging.getLogger(__name__).info(
                    "Detected correspondent: {}".format(correspondent.name)
                )
            else:
                logging.getLogger(__name__).info("Detected correspondent: -")
            document.correspondent = correspondent
        except Correspondent.DoesNotExist:
            logging.getLogger(__name__).warning(
                "Detected correspondent with id {} does not exist "
                "anymore! Did you delete it?".format(correspondent_id)
            )

    def _classify_document_type(self, X, document):
        y = self.document_type_classifier.predict(X)
        document_type_id = self.document_type_binarizer.inverse_transform(y)[0]
        try:
            document_type = None
            if document_type_id != -1:
                document_type = DocumentType.objects.get(id=document_type_id)
                logging.getLogger(__name__).info(
                    "Detected document type: {}".format(document_type.name)
                )
            else:
                logging.getLogger(__name__).info("Detected document type: -")
            document.document_type = document_type
        except DocumentType.DoesNotExist:
            logging.getLogger(__name__).warning(
                "Detected document type with id {} does not exist "
                "anymore! Did you delete it?".format(document_type_id)
            )

    def _classify_tags(self, X, document, replace_tags):
        y = self.tags_classifier.predict(X)
        tags_ids = self.tags_binarizer.inverse_transform(y)[0]
        if replace_tags:
            document.tags.clear()
        for tag_id in tags_ids:
            try:
                tag = Tag.objects.get(id=tag_id)
                logging.getLogger(__name__).info(
                    "Detected tag: {}".format(tag.name)
                )
                document.tags.add(tag)
            except Tag.DoesNotExist:
                logging.getLogger(__name__).warning(
                    "Detected tag with id {} does not exist anymore! Did "
                    "you delete it?".format(tag_id)
                )
