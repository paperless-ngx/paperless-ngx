import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { DocumentService } from 'src/app/services/rest/document.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-file-upload-widget',
  templateUrl: './file-upload-widget.component.html',
  styleUrls: ['./file-upload-widget.component.css']
})
export class FileUploadWidgetComponent implements OnInit {

  constructor(private documentService: DocumentService, private toastService: ToastService) { }

  ngOnInit(): void {
  }

  public fileOver(event){
    console.log(event);
  }
 
  public fileLeave(event){
    console.log(event);
  }
 
  public dropped(files: NgxFileDropEntry[]) {
    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry;
        console.log(fileEntry)
        fileEntry.file((file: File) => {
          console.log(file)
          const formData = new FormData()
          formData.append('document', file, file.name)
          this.documentService.uploadDocument(formData).subscribe(result => {
            this.toastService.showInfo("The document has been uploaded and will be processed by the consumer shortly.")
          }, error => {
            this.toastService.showError("An error has occured while uploading the document. Sorry!")
          })
        });
      }
    }
  }
}
