import logging
import os
import pickle

from documents.models import Correspondent, DocumentType, Tag, Document
from paperless import settings

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.naive_bayes import MultinomialNB
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
    type_binarizer = None

    tags_classifier = None
    correspondent_classifier = None
    type_classifier = None

    @staticmethod
    def load_classifier():
        clf = DocumentClassifier()
        clf.reload()
        return clf

    def reload(self):
        if self.classifier_version is None or os.path.getmtime(settings.MODEL_FILE) > self.classifier_version:
            print("reloading classifier")
            with open(settings.MODEL_FILE, "rb") as f:
                self.data_vectorizer = pickle.load(f)
                self.tags_binarizer = pickle.load(f)
                self.correspondent_binarizer = pickle.load(f)
                self.type_binarizer = pickle.load(f)

                self.tags_classifier = pickle.load(f)
                self.correspondent_classifier = pickle.load(f)
                self.type_classifier = pickle.load(f)
            self.classifier_version = os.path.getmtime(settings.MODEL_FILE)

    def save_classifier(self):
        with open(settings.MODEL_FILE, "wb") as f:
            pickle.dump(self.data_vectorizer, f)

            pickle.dump(self.tags_binarizer, f)
            pickle.dump(self.correspondent_binarizer, f)
            pickle.dump(self.type_binarizer, f)

            pickle.dump(self.tags_classifier, f)
            pickle.dump(self.correspondent_classifier, f)
            pickle.dump(self.type_classifier, f)

    def train(self):
        data = list()
        labels_tags = list()
        labels_correspondent = list()
        labels_type = list()

        # Step 1: Extract and preprocess training data from the database.
        logging.getLogger(__name__).info("Gathering data from database...")
        for doc in Document.objects.exclude(tags__is_inbox_tag=True):
            data.append(preprocess_content(doc.content))
            labels_type.append(doc.document_type.name if doc.document_type is not None else "-")
            labels_correspondent.append(doc.correspondent.name if doc.correspondent is not None else "-")
            tags = [tag.name for tag in doc.tags.all()]
            labels_tags.append(tags)

        # Step 2: vectorize data
        logging.getLogger(__name__).info("Vectorizing data...")
        self.data_vectorizer = CountVectorizer(analyzer='char', ngram_range=(2, 6), min_df=0.1)
        data_vectorized = self.data_vectorizer.fit_transform(data)

        self.tags_binarizer = MultiLabelBinarizer()
        labels_tags_vectorized = self.tags_binarizer.fit_transform(labels_tags)

        self.correspondent_binarizer = LabelBinarizer()
        labels_correspondent_vectorized = self.correspondent_binarizer.fit_transform(labels_correspondent)

        self.type_binarizer = LabelBinarizer()
        labels_type_vectorized = self.type_binarizer.fit_transform(labels_type)

        # Step 3: train the classifiers
        if len(self.tags_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training tags classifier...")
            self.tags_classifier = OneVsRestClassifier(MultinomialNB())
            self.tags_classifier.fit(data_vectorized, labels_tags_vectorized)
        else:
            self.tags_classifier = None
            logging.getLogger(__name__).info("There are no tags. Not training tags classifier.")

        if len(self.correspondent_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training correspondent classifier...")
            self.correspondent_classifier = OneVsRestClassifier(MultinomialNB())
            self.correspondent_classifier.fit(data_vectorized, labels_correspondent_vectorized)
        else:
            self.correspondent_classifier = None
            logging.getLogger(__name__).info("There are no correspondents. Not training correspondent classifier.")

        if len(self.type_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training document type classifier...")
            self.type_classifier = OneVsRestClassifier(MultinomialNB())
            self.type_classifier.fit(data_vectorized, labels_type_vectorized)
        else:
            self.type_classifier = None
            logging.getLogger(__name__).info("There are no document types. Not training document type classifier.")

    def classify_document(self, document, classify_correspondent=False, classify_type=False, classify_tags=False, replace_tags=False):
        X = self.data_vectorizer.transform([preprocess_content(document.content)])

        update_fields=()

        if classify_correspondent and self.correspondent_classifier is not None:
            y_correspondent = self.correspondent_classifier.predict(X)
            correspondent = self.correspondent_binarizer.inverse_transform(y_correspondent)[0]
            print("Detected correspondent:", correspondent)
            document.correspondent = Correspondent.objects.filter(name=correspondent).first()
            update_fields = update_fields + ("correspondent",)

        if classify_type and self.type_classifier is not None:
            y_type = self.type_classifier.predict(X)
            type = self.type_binarizer.inverse_transform(y_type)[0]
            print("Detected document type:", type)
            document.document_type = DocumentType.objects.filter(name=type).first()
            update_fields = update_fields + ("document_type",)

        if classify_tags and self.tags_classifier is not None:
            y_tags = self.tags_classifier.predict(X)
            tags = self.tags_binarizer.inverse_transform(y_tags)[0]
            print("Detected tags:", tags)
            if replace_tags:
                document.tags.clear()
            document.tags.add(*[Tag.objects.filter(name=t).first() for t in tags])

        document.save(update_fields=update_fields)
