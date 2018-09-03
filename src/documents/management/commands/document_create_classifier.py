import logging
import os.path
import pickle

from django.core.management.base import BaseCommand
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.preprocessing import MultiLabelBinarizer, LabelEncoder

from documents.models import Document
from ...mixins import Renderable


def preprocess_content(content):
    content = content.lower()
    content = content.strip()
    content = content.replace("\n", " ")
    content = content.replace("\r", " ")
    while content.find("  ") > -1:
        content = content.replace("  ", " ")
    return content


class Command(Renderable, BaseCommand):

    help = """
        There is no help.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):
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
        data_vectorizer = CountVectorizer(analyzer='char', ngram_range=(1, 5), min_df=0.05)
        data_vectorized = data_vectorizer.fit_transform(data)

        tags_binarizer = MultiLabelBinarizer()
        labels_tags_vectorized = tags_binarizer.fit_transform(labels_tags)

        correspondent_binarizer = LabelEncoder()
        labels_correspondent_vectorized = correspondent_binarizer.fit_transform(labels_correspondent)

        type_binarizer = LabelEncoder()
        labels_type_vectorized = type_binarizer.fit_transform(labels_type)

        # Step 3: train the classifiers
        if len(tags_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training tags classifier")
            tags_classifier = OneVsRestClassifier(MultinomialNB())
            tags_classifier.fit(data_vectorized, labels_tags_vectorized)
        else:
            tags_classifier = None
            logging.getLogger(__name__).info("There are no tags. Not training tags classifier.")

        if len(correspondent_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training correspondent classifier")
            correspondent_classifier = MultinomialNB()
            correspondent_classifier.fit(data_vectorized, labels_correspondent_vectorized)
        else:
            correspondent_classifier = None
            logging.getLogger(__name__).info("There are no correspondents. Not training correspondent classifier.")

        if len(type_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training document type classifier")
            type_classifier = MultinomialNB()
            type_classifier.fit(data_vectorized, labels_type_vectorized)
        else:
            type_classifier = None
            logging.getLogger(__name__).info("There are no document types. Not training document type classifier.")

        models_root = os.path.abspath(os.path.join(os.path.dirname(__name__), "..", "models", "models.pickle"))
        logging.getLogger(__name__).info("Saving models to " + models_root + "...")

        with open(models_root, "wb") as f:
            pickle.dump(data_vectorizer, f)

            pickle.dump(tags_binarizer, f)
            pickle.dump(correspondent_binarizer, f)
            pickle.dump(type_binarizer, f)

            pickle.dump(tags_classifier, f)
            pickle.dump(correspondent_classifier, f)
            pickle.dump(type_classifier, f)
