import { Clipboard } from '@angular/cdk/clipboard'
import { Component, effect, inject, input, signal } from '@angular/core'
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

  readonly id = input<number>(undefined)
  readonly subTitle = input('')
  readonly info = input<string>(undefined)
  readonly infoLink = input<string>(undefined)
  readonly loading = input(false)
  readonly title = input('')
  readonly copied = signal(false)
  private copyTimeout: any

  constructor() {
    effect(() => {
      this.titleService.setTitle(`${this.title()} - ${environment.appTitle}`)
    })
  }

  public copyID() {
    this.copied.set(this.clipboard.copy(this.id().toString()))
    clearTimeout(this.copyTimeout)
    this.copyTimeout = setTimeout(() => {
      this.copied.set(false)
    }, 3000)
  }
}
