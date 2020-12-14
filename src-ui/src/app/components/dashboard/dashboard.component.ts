import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';
import { environment } from 'src/environments/environment';


@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  constructor(
    private savedViewService: SavedViewService,
    private titleService: Title) { }


  savedViews: PaperlessSavedView[] = []

  ngOnInit(): void {
    this.savedViewService.listAll().subscribe(results => {
      this.savedViews = results.results.filter(savedView => savedView.show_on_dashboard)
    })
    this.titleService.setTitle(`Dashboard - ${environment.appTitle}`)
  }

}
