import logging
import os.path
import pickle

from django.core.management.base import BaseCommand
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.preprocessing import MultiLabelBinarizer, LabelEncoder

from documents.classifier import preprocess_content, DocumentClassifier
from documents.models import Document
from paperless import settings
from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        There is no help.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):
        clf = DocumentClassifier()

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
        clf.data_vectorizer = CountVectorizer(analyzer='char', ngram_range=(2, 6), min_df=0.1)
        data_vectorized = clf.data_vectorizer.fit_transform(data)

        print(clf.data_vectorizer.vocabulary_)

        logging.getLogger(__name__).info("Shape of vectorized data: {}".format(data_vectorized.shape))


        clf.tags_binarizer = MultiLabelBinarizer()
        labels_tags_vectorized = clf.tags_binarizer.fit_transform(labels_tags)

        clf.correspondent_binarizer = LabelEncoder()
        labels_correspondent_vectorized = clf.correspondent_binarizer.fit_transform(labels_correspondent)

        clf.type_binarizer = LabelEncoder()
        labels_type_vectorized = clf.type_binarizer.fit_transform(labels_type)

        # Step 3: train the classifiers
        if len(clf.tags_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training tags classifier")
            clf.tags_classifier = OneVsRestClassifier(MultinomialNB())
            clf.tags_classifier.fit(data_vectorized, labels_tags_vectorized)
        else:
            clf.tags_classifier = None
            logging.getLogger(__name__).info("There are no tags. Not training tags classifier.")

        if len(clf.correspondent_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training correspondent classifier")
            clf.correspondent_classifier = MultinomialNB()
            clf.correspondent_classifier.fit(data_vectorized, labels_correspondent_vectorized)
        else:
            clf.correspondent_classifier = None
            logging.getLogger(__name__).info("There are no correspondents. Not training correspondent classifier.")

        if len(clf.type_binarizer.classes_) > 0:
            logging.getLogger(__name__).info("Training document type classifier")
            clf.type_classifier = MultinomialNB()
            clf.type_classifier.fit(data_vectorized, labels_type_vectorized)
        else:
            clf.type_classifier = None
            logging.getLogger(__name__).info("There are no document types. Not training document type classifier.")

        logging.getLogger(__name__).info("Saving models to " + settings.MODEL_FILE + "...")

        clf.save_classifier()