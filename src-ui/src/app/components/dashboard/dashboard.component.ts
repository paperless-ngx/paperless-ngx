import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { Observable } from 'rxjs';
import { DocumentService } from 'src/app/services/rest/document.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { ToastService } from 'src/app/services/toast.service';
import { environment } from 'src/environments/environment';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {

  constructor(public savedViewConfigService: SavedViewConfigService) { }

  ngOnInit(): void {
  }

}
