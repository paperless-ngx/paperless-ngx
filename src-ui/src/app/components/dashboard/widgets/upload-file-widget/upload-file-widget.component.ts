import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { DocumentService } from 'src/app/services/rest/document.service';
import { Toast, ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-upload-file-widget',
  templateUrl: './upload-file-widget.component.html',
  styleUrls: ['./upload-file-widget.component.scss']
})
export class UploadFileWidgetComponent implements OnInit {

  constructor(private documentService: DocumentService, private toastService: ToastService) { }

  ngOnInit(): void {
  }

  public fileOver(event){
  }

  public fileLeave(event){
  }

  public dropped(files: NgxFileDropEntry[]) {
    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry;
        fileEntry.file((file: File) => {
          const formData = new FormData()
          formData.append('document', file, file.name)
          this.documentService.uploadDocument(formData).subscribe(result => {
            this.toastService.showInfo(The document has been uploaded and will be processed by the consumer shortly.")
          }, error => {
            switch (error.status) {
              case 400: {
                this.toastService.showError(`There was an error while uploading the document: ${error.error.document}`)
                break;
              }
              default: {
                this.toastService.showError("An error has occured while uploading the document. Sorry!")
                break;
              }
            }
          })
        });
      }
    }
  }
}
