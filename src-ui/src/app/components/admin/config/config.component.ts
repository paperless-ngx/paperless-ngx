import { Component, OnDestroy, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import {
  BehaviorSubject,
  Observable,
  Subject,
  Subscription,
  takeUntil,
} from 'rxjs'
import {
  ArchiveFileConfig,
  CleanConfig,
  ColorConvertConfig,
  ModeConfig,
  OutputTypeConfig,
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
  public ConfigChoices = {
    output_type: Object.values(OutputTypeConfig),
    mode: Object.values(ModeConfig),
    skip_archive_file: Object.values(ArchiveFileConfig),
    unpaper_clean: Object.values(CleanConfig),
    color_conversion_strategy: Object.values(ColorConvertConfig),
  }

  public configForm = new FormGroup({
    output_type: new FormControl(null),
    pages: new FormControl(null),
    language: new FormControl(null),
    mode: new FormControl(null),
    skip_archive_file: new FormControl(null),
    image_dpi: new FormControl(null),
    unpaper_clean: new FormControl(null),
    deskew: new FormControl(null),
    rotate_pages: new FormControl(null),
    rotate_pages_threshold: new FormControl(null),
    max_image_pixels: new FormControl(null),
    color_conversion_strategy: new FormControl(null),
    user_args: new FormControl(null),
  })

  public loading: boolean = false

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
    this.configService
      .getConfig()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (config) => {
          this.initialize(config)
        },
        error: (e) => {
          this.toastService.showError($localize`Error retrieving config`, e)
        },
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  private initialize(config: PaperlessConfig) {
    this.store = new BehaviorSubject(config)

    this.store
      .asObservable()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((state) => {
        this.configForm.patchValue(state, { emitEvent: false })
      })

    this.isDirty$ = dirtyCheck(this.configForm, this.store.asObservable())

    this.configForm.patchValue(config)
  }

  public saveConfig() {
    throw Error('Not Implemented')
  }
}
