import logging
import os
import pickle

from sklearn.neural_network import MLPClassifier

from documents.models import Correspondent, DocumentType, Tag, Document
from paperless import settings

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import MultiLabelBinarizer, LabelBinarizer


def preprocess_content(content):
    content = content.lower()
    content = content.strip()
    content = content.replace("\n", " ")
    content = content.replace("\r", " ")
    while content.find("  ") > -1:
        content = content.replace("  ", " ")
    return content


class DocumentClassifier(object):

    classifier_version = None

    data_vectorizer = None

    tags_binarizer = None
    correspondent_binarizer = None
    document_type_binarizer = None

    tags_classifier = None
    correspondent_classifier = None
    document_type_classifier = None

    @staticmethod
    def load_classifier():
        clf = DocumentClassifier()
        clf.reload()
        return clf

    def reload(self):
        if self.classifier_version is None or os.path.getmtime(settings.MODEL_FILE) > self.classifier_version:
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
            labels_document_type.append(doc.document_type.id if doc.document_type is not None and doc.document_type.automatic_classification else -1)
            labels_correspondent.append(doc.correspondent.id if doc.correspondent is not None and doc.correspondent.automatic_classification else -1)
            tags = [tag.id for tag in doc.tags.filter(automatic_classification=True)]
            labels_tags.append(tags)

        labels_tags_unique = set([tag for tags in labels_tags for tag in tags])
        logging.getLogger(__name__).info("{} documents, {} tag(s), {} correspondent(s), {} document type(s).".format(len(data), len(labels_tags_unique), len(set(labels_correspondent)), len(set(labels_document_type))))

        # Step 2: vectorize data
        logging.getLogger(__name__).info("Vectorizing data...")
        self.data_vectorizer = CountVectorizer(analyzer='char', ngram_range=(3, 5), min_df=0.1)
        data_vectorized = self.data_vectorizer.fit_transform(data)

        self.tags_binarizer = MultiLabelBinarizer()
        labels_tags_vectorized = self.tags_binarizer.fit_transform(labels_tags)

        self.correspondent_binarizer = LabelBinarizer()
        labels_correspondent_vectorized = self.correspondent_binarizer.fit_transform(labels_correspondent)

        self.document_type_binarizer = LabelBinarizer()
        labels_document_type_vectorized = self.document_type_binarizer.fit_transform(labels_document_type)

        # Step 3: train the classifiers
        if len(self.tags_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training tags classifier...")
            self.tags_classifier = MLPClassifier(verbose=True)
            self.tags_classifier.fit(data_vectorized, labels_tags_vectorized)
        else:
            self.tags_classifier = None
            logging.getLogger(__name__).info("There are no tags. Not training tags classifier.")

        if len(self.correspondent_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training correspondent classifier...")
            self.correspondent_classifier = MLPClassifier(verbose=True)
            self.correspondent_classifier.fit(data_vectorized, labels_correspondent_vectorized)
        else:
            self.correspondent_classifier = None
            logging.getLogger(__name__).info("There are no correspondents. Not training correspondent classifier.")

        if len(self.document_type_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training document type classifier...")
            self.document_type_classifier = MLPClassifier(verbose=True)
            self.document_type_classifier.fit(data_vectorized, labels_document_type_vectorized)
        else:
            self.document_type_classifier = None
            logging.getLogger(__name__).info("There are no document types. Not training document type classifier.")

    def classify_document(self, document, classify_correspondent=False, classify_document_type=False, classify_tags=False, replace_tags=False):
        X = self.data_vectorizer.transform([preprocess_content(document.content)])

        update_fields=()

        if classify_correspondent and self.correspondent_classifier is not None:
            y_correspondent = self.correspondent_classifier.predict(X)
            correspondent_id = self.correspondent_binarizer.inverse_transform(y_correspondent)[0]
            try:
                correspondent = Correspondent.objects.get(id=correspondent_id) if correspondent_id != -1 else None
                logging.getLogger(__name__).info("Detected correspondent: {}".format(correspondent.name if correspondent else "-"))
                document.correspondent = correspondent
                update_fields = update_fields + ("correspondent",)
            except Correspondent.DoesNotExist:
                logging.getLogger(__name__).warning("Detected correspondent with id {} does not exist anymore! Did you delete it?".format(correspondent_id))

        if classify_document_type and self.document_type_classifier is not None:
            y_type = self.document_type_classifier.predict(X)
            type_id = self.document_type_binarizer.inverse_transform(y_type)[0]
            try:
                document_type = DocumentType.objects.get(id=type_id) if type_id != -1 else None
                logging.getLogger(__name__).info("Detected document type: {}".format(document_type.name if document_type else "-"))
                document.document_type = document_type
                update_fields = update_fields + ("document_type",)
            except DocumentType.DoesNotExist:
                logging.getLogger(__name__).warning("Detected document type with id {} does not exist anymore! Did you delete it?".format(type_id))

        if classify_tags and self.tags_classifier is not None:
            y_tags = self.tags_classifier.predict(X)
            tags_ids = self.tags_binarizer.inverse_transform(y_tags)[0]
            if replace_tags:
                document.tags.clear()
            for tag_id in tags_ids:
                try:
                    tag = Tag.objects.get(id=tag_id)
                    document.tags.add(tag)
                    logging.getLogger(__name__).info("Detected tag: {}".format(tag.name))
                except Tag.DoesNotExist:
                    logging.getLogger(__name__).warning("Detected tag with id {} does not exist anymore! Did you delete it?".format(tag_id))

        document.save(update_fields=update_fields)
