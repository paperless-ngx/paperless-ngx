import ocrmypdf
from ocrmypdf import ocr, hookimpl
from ocrmypdf._concurrent import NullProgressBar


def get_unified_progress(self, desc, current, total):
    steps = ["Scanning contents", "OCR", "PDF/A conversion"]
    if desc in steps:
        index = steps.index(desc)
        return (index / len(steps)) + (current / total) / len(steps)
    else:
        return 0


class MyProgressBar:

    # __enter__, __exit__ and others removed for simplicity

    def update(self, *args, **kwargs):
        pass
        # i'd need to call MyOcrClass.progress() here.


@hookimpl
def get_progressbar_class(*args, **kwargs):
    return MyProgressBar


class MyOcrClass:

    def progress(self, current_p, max_p):
        # send progress over web sockets, *requires* self reference
        pass

    def run(self):
        ocrmypdf.ocr("test.pdf", "test_out.pdf", skip_text=True, jobs=1, plugins="test")


if __name__ == '__main__':
    MyOcrClass().run()
