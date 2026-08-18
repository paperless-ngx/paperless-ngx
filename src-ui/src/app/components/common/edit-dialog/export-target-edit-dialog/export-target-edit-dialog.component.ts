import { Component, ViewChild, inject, signal } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbAlert, NgbAlertModule } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import {
  EXPORT_TARGET_KINDS,
  ExportTarget,
  ExportTargetKind,
} from 'src/app/data/export-target'
import { ExportTargetService } from 'src/app/services/rest/export-target.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { NumberComponent } from '../../input/number/number.component'
import { PasswordComponent } from '../../input/password/password.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { TextAreaComponent } from '../../input/textarea/textarea.component'

const STORAGE_CLASS_OPTIONS = [
  { id: null, name: $localize`Bucket default` },
  { id: 'STANDARD', name: 'Standard' },
  { id: 'STANDARD_IA', name: 'Standard-IA' },
  { id: 'ONEZONE_IA', name: 'One Zone-IA' },
  { id: 'INTELLIGENT_TIERING', name: 'Intelligent-Tiering' },
  { id: 'GLACIER_IR', name: 'Glacier Instant Retrieval' },
  { id: 'GLACIER', name: 'Glacier Flexible Retrieval' },
  { id: 'DEEP_ARCHIVE', name: 'Glacier Deep Archive' },
]

@Component({
  selector: 'pngx-export-target-edit-dialog',
  templateUrl: './export-target-edit-dialog.component.html',
  styleUrls: ['./export-target-edit-dialog.component.scss'],
  imports: [
    TextComponent,
    TextAreaComponent,
    CheckComponent,
    NumberComponent,
    PasswordComponent,
    SelectComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbAlertModule,
  ],
})
export class ExportTargetEditDialogComponent extends EditDialogComponent<ExportTarget> {
  ExportTargetKind = ExportTargetKind

  testActive: boolean = false
  readonly testResult = signal<string>(undefined)
  readonly testMessage = signal<string>(undefined)
  alertTimeout

  @ViewChild('testResultAlert', { static: false }) testResultAlert: NgbAlert

  constructor() {
    super()
    this.service = inject(ExportTargetService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  getCreateTitle() {
    return $localize`Create new export target`
  }

  getEditTitle() {
    return $localize`Edit export target`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      kind: new FormControl(ExportTargetKind.S3),
      config: new FormGroup({
        bucket: new FormControl(null),
        prefix: new FormControl(null),
        endpoint: new FormControl(null),
        region: new FormControl(null),
        storage_class: new FormControl(null),
        host: new FormControl(null),
        port: new FormControl(null),
        path: new FormControl(null),
      }),
      access_key: new FormControl(null),
      secret_key: new FormControl(null),
      private_key: new FormControl(null),
      retention_days: new FormControl(null),
      enabled: new FormControl(true),
    })
  }

  get kindOptions() {
    return EXPORT_TARGET_KINDS
  }

  get storageClassOptions() {
    return STORAGE_CLASS_OPTIONS
  }

  get kind(): ExportTargetKind {
    return this.objectForm.get('kind').value
  }

  protected getFormValues(): any {
    const values = super.getFormValues()
    if (values.config) {
      // preserve server-managed config keys, e.g. the pinned SFTP host key
      values.config = Object.assign(
        {},
        this.object?.config ?? {},
        values.config
      )
    }
    return values
  }

  test() {
    this.testActive = true
    this.testResult.set(null)
    clearTimeout(this.alertTimeout)
    const exportTargetService = this.service as ExportTargetService
    const newObject = Object.assign(
      Object.assign({}, this.object),
      this.getFormValues()
    )
    exportTargetService.test(newObject).subscribe({
      next: (result: { success: boolean }) => {
        this.testActive = false
        this.testResult.set(result.success ? 'success' : 'danger')
        this.testMessage.set(
          result.success
            ? $localize`Successfully connected to the export target`
            : $localize`Unable to connect to the export target`
        )
        this.alertTimeout = setTimeout(() => this.testResultAlert.close(), 5000)
      },
      error: (e) => {
        this.testActive = false
        this.testResult.set('danger')
        this.testMessage.set(
          typeof e.error === 'string' && e.error.length
            ? e.error
            : $localize`Unable to connect to the export target`
        )
        this.alertTimeout = setTimeout(
          () => this.testResultAlert.close(),
          10000
        )
      },
    })
  }
}
