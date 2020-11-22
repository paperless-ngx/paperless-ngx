import { Component, OnInit } from '@angular/core';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';


@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  constructor(
    public savedViewConfigService: SavedViewConfigService) { }


  savedViews = []

  ngOnInit(): void {
    this.savedViews = this.savedViewConfigService.getDashboardConfigs()
  }

}
