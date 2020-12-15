import { Component, OnInit } from '@angular/core';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';


@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  constructor(
    private savedViewService: SavedViewService) { }


  savedViews: PaperlessSavedView[] = []

  ngOnInit(): void {
    this.savedViewService.listAll().subscribe(results => {
      this.savedViews = results.results.filter(savedView => savedView.show_on_dashboard)
    })
  }

}
