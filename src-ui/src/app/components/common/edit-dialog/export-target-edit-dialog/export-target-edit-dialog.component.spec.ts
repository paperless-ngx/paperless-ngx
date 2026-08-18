import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { ExportTargetKind } from 'src/app/data/export-target'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'
import { CheckComponent } from '../../input/check/check.component'
import { NumberComponent } from '../../input/number/number.component'
import { PasswordComponent } from '../../input/password/password.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { TextAreaComponent } from '../../input/textarea/textarea.component'
import { EditDialogMode } from '../edit-dialog.component'
import { ExportTargetEditDialogComponent } from './export-target-edit-dialog.component'

describe('ExportTargetEditDialogComponent', () => {
  let component: ExportTargetEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<ExportTargetEditDialogComponent>
  let httpController: HttpTestingController

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        ExportTargetEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        TextAreaComponent,
        CheckComponent,
        NumberComponent,
        PasswordComponent,
      ],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    httpController = TestBed.inject(HttpTestingController)

    fixture = TestBed.createComponent(ExportTargetEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser.set({ id: 99, username: 'user99' })
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode.set(EditDialogMode.CREATE)
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode.set(EditDialogMode.EDIT)
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should switch fields on kind', () => {
    component.objectForm.get('kind').setValue(ExportTargetKind.S3)
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Bucket')
    component.objectForm.get('kind').setValue(ExportTargetKind.SFTP)
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Host')
    component.objectForm.get('kind').setValue(ExportTargetKind.Local)
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Path')
  })

  it('should preserve server-managed config keys on save', () => {
    component.object = {
      id: 1,
      name: 'NAS',
      kind: ExportTargetKind.SFTP,
      config: { host: 'nas.local', host_key: 'ssh-ed25519 AAAA' },
      enabled: true,
    }
    component.objectForm.get('kind').setValue(ExportTargetKind.SFTP)
    component.objectForm.get('config').patchValue({ host: 'nas2.local' })
    const values = component['getFormValues']()
    expect(values.config.host).toEqual('nas2.local')
    expect(values.config.host_key).toEqual('ssh-ed25519 AAAA')
  })

  it('should support test connection and show result', () => {
    jest.useFakeTimers()
    component.object = {
      name: 'Bucket',
      kind: ExportTargetKind.S3,
      config: { bucket: 'docs' },
      enabled: true,
    }

    // success
    component.test()
    httpController
      .expectOne(`${environment.apiBaseUrl}export_targets/test/`)
      .flush({ success: true })
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain(
      'Successfully connected'
    )
    jest.advanceTimersByTime(6000)
    fixture.detectChanges()

    // error with message
    component.test()
    httpController
      .expectOne(`${environment.apiBaseUrl}export_targets/test/`)
      .flush('S3 connection test failed', { status: 400, statusText: 'error' })
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain(
      'S3 connection test failed'
    )
    jest.advanceTimersByTime(11000)
    jest.useRealTimers()
  })
})
