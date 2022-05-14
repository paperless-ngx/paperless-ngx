import { Component, OnInit } from '@angular/core'
import { Meta } from '@angular/platform-browser'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent {
  constructor(public savedViewService: SavedViewService, private meta: Meta) {}

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
      return $localize`Hello ${this.displayName}, welcome to Paperless-ngx!`
    } else {
      return $localize`Welcome to Paperless-ngx!`
    }
  }
}
