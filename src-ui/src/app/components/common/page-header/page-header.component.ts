import { Clipboard } from '@angular/cdk/clipboard'
import { Component, Input, inject, signal } from '@angular/core'
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

  private titleSignal = signal('')
  private idSignal = signal<number>(undefined)
  private subTitleSignal = signal('')
  private infoSignal = signal<string>(undefined)
  private infoLinkSignal = signal<string>(undefined)
  private loadingSignal = signal(false)
  private copiedSignal = signal(false)
  private copyTimeout: any

  public get copied(): boolean {
    return this.copiedSignal()
  }

  public set copied(copied: boolean) {
    this.copiedSignal.set(copied)
  }

  @Input()
  set title(title: string) {
    this.titleSignal.set(title)
    this.titleService.setTitle(`${this.title} - ${environment.appTitle}`)
  }

  get title() {
    return this.titleSignal()
  }

  @Input()
  get id(): number {
    return this.idSignal()
  }

  set id(id: number) {
    this.idSignal.set(id)
  }

  @Input()
  get subTitle(): string {
    return this.subTitleSignal()
  }

  set subTitle(subTitle: string) {
    this.subTitleSignal.set(subTitle)
  }

  @Input()
  get info(): string {
    return this.infoSignal()
  }

  set info(info: string) {
    this.infoSignal.set(info)
  }

  @Input()
  get infoLink(): string {
    return this.infoLinkSignal()
  }

  set infoLink(infoLink: string) {
    this.infoLinkSignal.set(infoLink)
  }

  @Input()
  get loading(): boolean {
    return this.loadingSignal()
  }

  set loading(loading: boolean) {
    this.loadingSignal.set(loading)
  }

  public copyID() {
    this.copied = this.clipboard.copy(this.id.toString())
    clearTimeout(this.copyTimeout)
    this.copyTimeout = setTimeout(() => {
      this.copied = false
    }, 3000)
  }
}
