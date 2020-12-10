import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { environment } from 'src/environments/environment';


@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  constructor(
    public savedViewConfigService: SavedViewConfigService,
    private titleService: Title) { }


  savedViews = []

  ngOnInit(): void {
    this.savedViews = this.savedViewConfigService.getDashboardConfigs()
    this.titleService.setTitle(`Dashboard - ${environment.appTitle}`)
  }

}
