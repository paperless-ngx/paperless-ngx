import os
import pickle

from documents.models import Correspondent, DocumentType, Tag
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

    def classify_document(self, document, classify_correspondent=False, classify_type=False, classify_tags=False):
        X = self.data_vectorizer.transform([preprocess_content(document.content)])

        update_fields=()

        if classify_correspondent:
            y_correspondent = self.correspondent_classifier.predict(X)
            correspondent = self.correspondent_binarizer.inverse_transform(y_correspondent)[0]
            print("Detected correspondent:", correspondent)
            document.correspondent = Correspondent.objects.filter(name=correspondent).first()
            update_fields = update_fields + ("correspondent",)

        if classify_type:
            y_type = self.type_classifier.predict(X)
            type = self.type_binarizer.inverse_transform(y_type)[0]
            print("Detected document type:", type)
            document.document_type = DocumentType.objects.filter(name=type).first()
            update_fields = update_fields + ("document_type",)

        if classify_tags:
            y_tags = self.tags_classifier.predict(X)
            tags = self.tags_binarizer.inverse_transform(y_tags)[0]
            print("Detected tags:", tags)
            document.tags.add(*[Tag.objects.filter(name=t).first() for t in tags])

        document.save(update_fields=update_fields)
