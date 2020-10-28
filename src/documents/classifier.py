import logging
import os
import pickle

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import MultiLabelBinarizer, LabelBinarizer

from documents.models import Document, MatchingModel
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
        self.X = None

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
                if doc.document_type.matching_algorithm == MatchingModel.MATCH_AUTO:
                    y = doc.document_type.id
            labels_document_type.append(y)

            y = -1
            if doc.correspondent:
                if doc.correspondent.matching_algorithm == MatchingModel.MATCH_AUTO:
                    y = doc.correspondent.id
            labels_correspondent.append(y)

            tags = [tag.id for tag in doc.tags.filter(
                matching_algorithm=MatchingModel.MATCH_AUTO
            )]
            labels_tags.append(tags)

        if not data:
            raise ValueError("No training data available.")

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

    def update(self, document):
        self.X = self.data_vectorizer.transform(
            [preprocess_content(document.content)]
        )

    def predict_correspondent(self):
        if self.correspondent_classifier:
            y = self.correspondent_classifier.predict(self.X)
            correspondent_id = self.correspondent_binarizer.inverse_transform(y)[0]
            if correspondent_id != -1:
                return correspondent_id
            else:
                return None
        else:
            return None

    def predict_document_type(self):
        if self.document_type_classifier:
            y = self.document_type_classifier.predict(self.X)
            document_type_id = self.document_type_binarizer.inverse_transform(y)[0]
            if document_type_id != -1:
                return document_type_id
            else:
                return None
        else:
            return None

    def predict_tags(self):
        if self.tags_classifier:
            y = self.tags_classifier.predict(self.X)
            tags_ids = self.tags_binarizer.inverse_transform(y)[0]
            return tags_ids
        else:
            return []
