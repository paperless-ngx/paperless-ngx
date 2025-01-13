import { Component, Input } from '@angular/core'
import { Title } from '@angular/platform-browser'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrapModule } from 'ngx-ui-tour-ng-bootstrap'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-page-header',
  templateUrl: './page-header.component.html',
  styleUrls: ['./page-header.component.scss'],
  imports: [NgbPopoverModule, NgxBootstrapIconsModule, TourNgBootstrapModule],
})
export class PageHeaderComponent {
  constructor(private titleService: Title) {}

  _title = ''

  @Input()
  set title(title: string) {
    this._title = title
    this.titleService.setTitle(`${this.title} - ${environment.appTitle}`)
  }

  get title() {
    return this._title
  }

  @Input()
  subTitle: string = ''

  @Input()
  info: string

  @Input()
  infoLink: string
}
