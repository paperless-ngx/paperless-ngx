import { Component, OnInit } from '@angular/core';
import { Meta } from '@angular/platform-browser';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { SavedViewService } from 'src/app/services/rest/saved-view.service';


@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  constructor(
    private savedViewService: SavedViewService,
    private meta: Meta
  ) { }

  get displayName() {
    let tagFullName = this.meta.getTag('name=full_name')
    let tagUsername = this.meta.getTag('name=username')
    if (tagFullName && tagFullName.content) {
      return tagFullName.content
    } else if (tagUsername && tagUsername.content) {
      return tagUsername.content
    } else {
      return null
    }
  }

  get subtitle() {
    if (this.displayName) {
      return $localize`Hello ${this.displayName}, welcome to Paperless-ng!`
    } else {
      return $localize`Welcome to Paperless-ng!`
    }
  }

  savedViews: PaperlessSavedView[] = []

  ngOnInit(): void {
    this.savedViewService.listAll().subscribe(results => {
      this.savedViews = results.results.filter(savedView => savedView.show_on_dashboard)
    })
  }

}
