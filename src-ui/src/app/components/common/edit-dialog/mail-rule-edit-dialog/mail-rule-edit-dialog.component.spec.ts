import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectComponent, NgSelectModule } from '@ng-select/ng-select'
import { of, throwError } from 'rxjs'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import {
  MailAction,
  MailMetadataCorrespondentOption,
} from 'src/app/data/mail-rule'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { CheckComponent } from '../../input/check/check.component'
import { NumberComponent } from '../../input/number/number.component'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { SwitchComponent } from '../../input/switch/switch.component'
import { TagsComponent } from '../../input/tags/tags.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import { MailRuleEditDialogComponent } from './mail-rule-edit-dialog.component'

describe('MailRuleEditDialogComponent', () => {
  let component: MailRuleEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<MailRuleEditDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        MailRuleEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PermissionsFormComponent,
        NumberComponent,
        TagsComponent,
        CheckComponent,
        SwitchComponent,
      ],
      providers: [
        NgbActiveModal,
        {
          provide: MailAccountService,
          useValue: {
            listAll: () => of([]),
          },
        },
        {
          provide: CorrespondentService,
          useValue: {
            listAll: () => of([]),
          },
        },
        {
          provide: DocumentTypeService,
          useValue: {
            listAll: () => of([]),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(MailRuleEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser.set({ id: 99, username: 'user99' })
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should use empty related object lists when retrieval fails', () => {
    const failed = () => throwError(() => new Error('Forbidden'))
    const toastSpy = jest.spyOn(TestBed.inject(ToastService), 'showError')
    jest
      .spyOn(TestBed.inject(MailAccountService), 'listAll')
      .mockReturnValue(failed())
    jest
      .spyOn(TestBed.inject(CorrespondentService), 'listAll')
      .mockReturnValue(failed())
    jest
      .spyOn(TestBed.inject(DocumentTypeService), 'listAll')
      .mockReturnValue(failed())

    const failedFixture = TestBed.createComponent(MailRuleEditDialogComponent)
    const failedComponent = failedFixture.componentInstance

    expect(failedComponent.accounts()).toEqual([])
    expect(failedComponent.correspondents()).toEqual([])
    expect(failedComponent.documentTypes()).toEqual([])
    expect(() => failedFixture.detectChanges()).not.toThrow()
    expect(toastSpy).toHaveBeenCalledTimes(3)
    expect(toastSpy).toHaveBeenCalledWith(
      'Error retrieving mail accounts',
      expect.any(Error)
    )
    expect(toastSpy).toHaveBeenCalledWith(
      'Error retrieving correspondents',
      expect.any(Error)
    )
    expect(toastSpy).toHaveBeenCalledWith(
      'Error retrieving document types',
      expect.any(Error)
    )
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

  it('should offer only document link fields when editing a mail rule', () => {
    TestBed.inject(PermissionsService).initialize(
      ['view_mailrule', 'change_mailrule', 'view_customfield'],
      settingsService.currentUser()
    )
    const listFields = jest.spyOn(
      TestBed.inject(CustomFieldsService),
      'listAll'
    )
    for (const linkFieldName of ['同封邮件', '相关单据']) {
      listFields.mockReturnValue(
        of({
          count: 2,
          results: [
            {
              id: 1,
              name: linkFieldName,
              data_type: CustomFieldDataType.DocumentLink,
            },
            { id: 2, name: '备注', data_type: CustomFieldDataType.String },
          ],
        })
      )
      const dialog = TestBed.createComponent(MailRuleEditDialogComponent)
      dialog.componentInstance.dialogMode.set(EditDialogMode.EDIT)
      dialog.detectChanges()

      const picker = dialog.debugElement.query(
        By.css('[formControlName="same_email_link_field"]')
      )
      expect(picker).not.toBeNull()
      picker.query(By.directive(NgSelectComponent)).componentInstance.open()
      dialog.detectChanges()
      const options = picker
        .queryAll(By.css('.ng-option'))
        .map((option) => option.nativeElement.textContent.trim())
      expect(options).toContain(linkFieldName)
      expect(options).not.toContain('备注')
      dialog.destroy()
    }
  })

  it('should not fetch or show custom fields for a rule editor without view permission', () => {
    const editor = settingsService.currentUser()
    TestBed.inject(PermissionsService).initialize(
      ['view_mailrule', 'change_mailrule'],
      editor
    )
    const listFields = jest
      .spyOn(TestBed.inject(CustomFieldsService), 'listAll')
      .mockReturnValue(throwError(() => new Error('Forbidden')))
    const dialog = TestBed.createComponent(MailRuleEditDialogComponent)
    dialog.componentInstance.dialogMode.set(EditDialogMode.EDIT)
    dialog.componentInstance.object = {
      ...dialog.componentInstance.objectForm.getRawValue(),
      id: 1,
      name: 'Existing rule',
      owner: editor.id,
      same_email_link_field: null,
    }
    dialog.detectChanges()

    expect(listFields).not.toHaveBeenCalled()
    expect(
      dialog.debugElement.query(
        By.css('[formControlName="same_email_link_field"]')
      )
    ).toBeNull()
  })

  it('should support optional fields', () => {
    expect(component.showCorrespondentField).toBeFalsy()
    component.objectForm
      .get('assign_correspondent_from')
      .setValue(MailMetadataCorrespondentOption.FromCustom)
    expect(component.showCorrespondentField).toBeTruthy()

    expect(component.showActionParamField).toBeFalsy()
    component.objectForm.get('action').setValue(MailAction.Move)
    expect(component.showActionParamField).toBeTruthy()
    component.objectForm.get('action').setValue('')
    expect(component.showActionParamField).toBeFalsy()
    component.objectForm.get('action').setValue(MailAction.Tag)
    expect(component.showActionParamField).toBeTruthy()

    // coverage of optional chaining
    component.objectForm = null
    expect(component.showCorrespondentField).toBeFalsy()
    expect(component.showActionParamField).toBeFalsy()
  })
})
