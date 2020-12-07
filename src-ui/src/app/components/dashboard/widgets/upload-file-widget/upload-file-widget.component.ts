import { HttpEventType } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { DocumentService } from 'src/app/services/rest/document.service';
import { Toast, ToastService } from 'src/app/services/toast.service';


interface UploadStatus {
  file: string
  loaded: number
  total: number 
}

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

  uploadStatus: UploadStatus[] = []

  uploadVisible = false

  get loadedSum() {
    return this.uploadStatus.map(s => s.loaded).reduce((a,b) => a+b, 1)
  }

  get totalSum() {
    return this.uploadStatus.map(s => s.total).reduce((a,b) => a+b, 1)
  }

  public dropped(files: NgxFileDropEntry[]) {
    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry;
        fileEntry.file((file: File) => {
          let formData = new FormData()
          formData.append('document', file, file.name)

          let uploadStatusObject: UploadStatus = {file: file.name, loaded: 0, total: 1}
          this.uploadStatus.push(uploadStatusObject)
          this.uploadVisible = true
          this.documentService.uploadDocument(formData).subscribe(event => {
            if (event.type == HttpEventType.UploadProgress) {
              uploadStatusObject.loaded = event.loaded
              uploadStatusObject.total = event.total
            } else if (event.type == HttpEventType.Response) {
              this.uploadStatus.splice(this.uploadStatus.indexOf(uploadStatusObject), 1)
              this.toastService.showToast(Toast.make("Information", "The document has been uploaded and will be processed by the consumer shortly."))
            }
            
          }, error => {
            this.uploadStatus.splice(this.uploadStatus.indexOf(uploadStatusObject), 1)
            switch (error.status) {
              case 400: {
                this.toastService.showToast(Toast.makeError(`There was an error while uploading the document: ${error.error.document}`))
                break;
              }
              default: {
                this.toastService.showToast(Toast.makeError("An error has occured while uploading the document. Sorry!"))
                break;
              }
            }
          })
        });
      }
    }
  }
}
