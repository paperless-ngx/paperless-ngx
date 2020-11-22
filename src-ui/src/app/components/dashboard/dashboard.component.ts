import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { Observable } from 'rxjs';
import { DocumentService } from 'src/app/services/rest/document.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
import { environment } from 'src/environments/environment';

export interface Statistics {
  documents_total?: number
  documents_inbox?: number
}

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  constructor(private documentService: DocumentService, private toastService: ToastService,
    public savedViewConfigService: SavedViewConfigService, private http: HttpClient) { }


  savedDashboardViews = []
  statistics: Statistics = {}

  ngOnInit(): void {
    this.savedViewConfigService.getDashboardConfigs().forEach(config => {
      this.documentService.list(1,10,config.sortField,config.sortDirection,config.filterRules).subscribe(result => {
        this.savedDashboardViews.push({viewConfig: config, documents: result.results})
      })
    })
    this.getStatistics().subscribe(statistics => {
      this.statistics = statistics
    })
  }

  getStatistics(): Observable<Statistics> {
    return this.http.get(`${environment.apiBaseUrl}statistics/`)
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
            this.toastService.showToast(Toast.make("Information", "The document has been uploaded and will be processed by the consumer shortly."))
          }, error => {
            this.toastService.showToast(Toast.makeError("An error has occured while uploading the document. Sorry!"))
          })
        });
      }
    }
  }
}
