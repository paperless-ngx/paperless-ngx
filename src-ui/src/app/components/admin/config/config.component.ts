import { Component, OnDestroy, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import {
  BehaviorSubject,
  Observable,
  Subject,
  Subscription,
  first,
  takeUntil,
} from 'rxjs'
import {
  PaperlessConfigOptions,
  ConfigCategory,
  ConfigOption,
  ConfigOptionType,
  PaperlessConfig,
} from 'src/app/data/paperless-config'
import { ConfigService } from 'src/app/services/config.service'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { DirtyComponent, dirtyCheck } from '@ngneat/dirty-check-forms'

@Component({
  selector: 'pngx-config',
  templateUrl: './config.component.html',
  styleUrl: './config.component.scss',
})
export class ConfigComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy, DirtyComponent
{
  public readonly ConfigOptionType = ConfigOptionType

  public configForm = new FormGroup({
    id: new FormControl(),
    output_type: new FormControl(),
    pages: new FormControl(),
    language: new FormControl(),
    mode: new FormControl(),
    skip_archive_file: new FormControl(),
    image_dpi: new FormControl(),
    unpaper_clean: new FormControl(),
    deskew: new FormControl(),
    rotate_pages: new FormControl(),
    rotate_pages_threshold: new FormControl(),
    max_image_pixels: new FormControl(),
    color_conversion_strategy: new FormControl(),
    user_args: new FormControl(),
  })

  get optionCategories(): string[] {
    return Object.values(ConfigCategory)
  }

  getCategoryOptions(category: string): ConfigOption[] {
    return PaperlessConfigOptions.filter((o) => o.category === category)
  }

  public loading: boolean = false

  initialConfig: PaperlessConfig
  store: BehaviorSubject<any>
  storeSub: Subscription
  isDirty$: Observable<boolean>

  private unsubscribeNotifier: Subject<any> = new Subject()

  constructor(
    private configService: ConfigService,
    private toastService: ToastService
  ) {
    super()
  }

  ngOnInit(): void {
    this.loading = true
    this.configService
      .getConfig()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (config) => {
          this.loading = false
          this.initialize(config)
        },
        error: (e) => {
          this.loading = false
          this.toastService.showError($localize`Error retrieving config`, e)
        },
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  private initialize(config: PaperlessConfig) {
    if (!this.store) {
      this.store = new BehaviorSubject(config)

      this.store
        .asObservable()
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((state) => {
          this.configForm.patchValue(state, { emitEvent: false })
        })

      this.isDirty$ = dirtyCheck(this.configForm, this.store.asObservable())
    }

    this.configForm.patchValue(config)

    this.initialConfig = config
  }

  getDocsUrl(key: string) {
    return `https://docs.paperless-ngx.com/configuration/#${key}`
  }

  public saveConfig() {
    this.loading = true
    this.configService
      .saveConfig(this.configForm.value as PaperlessConfig)
      .pipe(takeUntil(this.unsubscribeNotifier), first())
      .subscribe({
        next: (config) => {
          this.loading = false
          this.initialize(config)
          this.store.next(config)
          this.toastService.showInfo($localize`Configuration updated`)
        },
        error: (e) => {
          this.loading = false
          this.toastService.showError(
            $localize`An error occurred updating configuration`,
            e
          )
        },
      })
  }

  public discardChanges() {
    this.configForm.reset(this.initialConfig)
  }
}
