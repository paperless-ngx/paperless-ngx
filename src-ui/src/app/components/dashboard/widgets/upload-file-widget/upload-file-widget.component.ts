import { HttpEventType } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { ConsumerStatusService, FileStatus, FileStatusPhase } from 'src/app/services/consumer-status.service';
import { DocumentService } from 'src/app/services/rest/document.service';


@Component({
  selector: 'app-upload-file-widget',
  templateUrl: './upload-file-widget.component.html',
  styleUrls: ['./upload-file-widget.component.scss']
})
export class UploadFileWidgetComponent implements OnInit {

  constructor(
    private documentService: DocumentService,
    private consumerStatusService: ConsumerStatusService
  ) { }

  getStatus() {
    return this.consumerStatusService.consumerStatus
  }

  isFinished(status: FileStatus) {
    return status.phase == FileStatusPhase.FAILED || status.phase == FileStatusPhase.SUCCESS
  }

  getType(status: FileStatus) {
    switch (status.phase) {
      case FileStatusPhase.PROCESSING:
      case FileStatusPhase.UPLOADING:
          return "primary"
      case FileStatusPhase.FAILED:
        return "danger"
      case FileStatusPhase.SUCCESS:
        return "success"
    }
  }

  dismiss(status: FileStatus) {
    this.consumerStatusService.dismiss(status)
  }
  
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
          let formData = new FormData()
          formData.append('document', file, file.name)
          let status = this.consumerStatusService.newFileUpload()
          status.filename = file.name

          this.documentService.uploadDocument(formData).subscribe(event => {
            if (event.type == HttpEventType.UploadProgress) {
              status.updateProgress(FileStatusPhase.UPLOADING, event.loaded, event.total)
            } else if (event.type == HttpEventType.Response) {
              status.taskId = event.body["task_id"]
            }

          }, error => {
            status.updateProgress(FileStatusPhase.FAILED)
            switch (error.status) {
              case 400: {
                status.message = error.error.document
                break;
              }
              default: {
                status.message = $localize`An error has occurred while uploading the document. Sorry!`
                break;
              }
            }

          })
        });
      }
    }
  }
}
