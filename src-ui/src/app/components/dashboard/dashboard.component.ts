import { Component, OnInit } from '@angular/core';
import { FileSystemDirectoryEntry, FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {

  constructor(private documentService: DocumentService) { }

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
 
      // Is it a file?
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry;
        console.log(fileEntry)
        fileEntry.file((file: File) => {
          console.log(file)
          const formData = new FormData()
          formData.append('document', file, file.name)
          this.documentService.uploadDocument(formData).subscribe(result => {
            console.log(result)
          }, error => {
            console.error(error)
          })
        });
      }
    }
  }
}
