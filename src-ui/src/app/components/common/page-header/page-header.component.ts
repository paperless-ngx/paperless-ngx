import { Clipboard } from '@angular/cdk/clipboard'
import { Component, Input, inject } from '@angular/core'
import { Title } from '@angular/platform-browser'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrap } from 'ngx-ui-tour-ng-bootstrap'
import { environment } from 'src/environments/environment'

@Component({
  selector: 'pngx-page-header',
  templateUrl: './page-header.component.html',
  styleUrls: ['./page-header.component.scss'],
  imports: [NgbPopoverModule, NgxBootstrapIconsModule, TourNgBootstrap],
})
export class PageHeaderComponent {
  private titleService = inject(Title)
  private clipboard = inject(Clipboard)

  private _title = ''
  public copied: boolean = false
  private copyTimeout: any

  @Input()
  set title(title: string) {
    this._title = title
    this.titleService.setTitle(`${this.title} - ${environment.appTitle}`)
  }

  get title() {
    return this._title
  }

  @Input()
  id: number

  @Input()
  subTitle: string = ''

  @Input()
  info: string

  @Input()
  infoLink: string

  @Input()
  loading: boolean = false

  public copyID() {
    this.copied = this.clipboard.copy(this.id.toString())
    clearTimeout(this.copyTimeout)
    this.copyTimeout = setTimeout(() => {
      this.copied = false
    }, 3000)
  }
}
