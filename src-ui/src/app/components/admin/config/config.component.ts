import { Component, OnDestroy, OnInit } from '@angular/core'
import { AbstractControl, FormControl, FormGroup } from '@angular/forms'
import {
  BehaviorSubject,
  Observable,
  Subject,
  Subscription,
  first,
  takeUntil,
} from 'rxjs'
import {
  EdocConfigOptions,
  ConfigCategory,
  ConfigOption,
  ConfigOptionType,
  EdocConfig,
} from 'src/app/data/edoc-config'
import { ConfigService } from 'src/app/services/config.service'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { DirtyComponent, dirtyCheck } from '@ngneat/dirty-check-forms'
import { SettingsService } from 'src/app/services/settings.service'

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

  // generated dynamically
  public configForm = new FormGroup({})

  public errors = {}

  get optionCategories(): string[] {
    return Object.values(ConfigCategory)
  }

  getCategoryOptions(category: string): ConfigOption[] {
    return EdocConfigOptions.filter((o) => o.category === category)
  }

  public loading: boolean = false

  initialConfig: EdocConfig
  store: BehaviorSubject<any>
  storeSub: Subscription
  isDirty$: Observable<boolean>

  private unsubscribeNotifier: Subject<any> = new Subject()

  constructor(
    private configService: ConfigService,
    private toastService: ToastService,
    private settingsService: SettingsService
  ) {
    super()
    this.configForm.addControl('id', new FormControl())
    EdocConfigOptions.forEach((option) => {
      this.configForm.addControl(option.key, new FormControl())
    })
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

    // validate JSON inputs
    EdocConfigOptions.filter(
      (o) => o.type === ConfigOptionType.JSON
    ).forEach((option) => {
      this.configForm
        .get(option.key)
        .addValidators((control: AbstractControl) => {
          if (!control.value || control.value.toString().length === 0)
            return null
          try {
            JSON.parse(control.value)
          } catch (e) {
            return [
              {
                user_args: e,
              },
            ]
          }
          return null
        })
      this.configForm.get(option.key).statusChanges.subscribe((status) => {
        this.errors[option.key] =
          status === 'INVALID' ? $localize`Invalid JSON` : null
      })
      this.configForm.get(option.key).updateValueAndValidity()
    })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  private initialize(config: EdocConfig) {
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
      .saveConfig(this.configForm.value as EdocConfig)
      .pipe(takeUntil(this.unsubscribeNotifier), first())
      .subscribe({
        next: (config) => {
          this.loading = false
          this.initialize(config)
          this.store.next(config)
          this.settingsService.initializeSettings().subscribe()
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

  public uploadFile(file: File, key: string) {
    this.loading = true
    this.configService
      .uploadFile(file, this.configForm.value['id'], key)
      .pipe(takeUntil(this.unsubscribeNotifier), first())
      .subscribe({
        next: (config) => {
          this.loading = false
          this.initialize(config)
          this.store.next(config)
          this.settingsService.initializeSettings().subscribe()
          this.toastService.showInfo($localize`File successfully updated`)
        },
        error: (e) => {
          this.loading = false
          this.toastService.showError(
            $localize`An error occurred uploading file`,
            e
          )
        },
      })
  }
}
