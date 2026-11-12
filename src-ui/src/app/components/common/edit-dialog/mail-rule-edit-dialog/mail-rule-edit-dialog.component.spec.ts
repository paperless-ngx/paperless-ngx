import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of, throwError } from 'rxjs'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import {
  MailAction,
  MailMetadataCorrespondentOption,
} from 'src/app/data/mail-rule'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
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
        {
          provide: CustomFieldsService,
          useValue: {
            listAll: () =>
              of({
                count: 2,
                results: [
                  {
                    id: 1,
                    name: 'Reference',
                    data_type: CustomFieldDataType.String,
                  },
                  {
                    id: 2,
                    name: 'Related documents',
                    data_type: CustomFieldDataType.DocumentLink,
                  },
                ],
              }),
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

  function getDocumentLinkSelect(targetFixture = fixture): SelectComponent {
    return targetFixture.debugElement.query(
      By.css('pngx-input-select[formControlName="assign_document_link_field"]')
    ).componentInstance
  }

  it('should offer only document link fields and leave linking off by default', () => {
    const select = getDocumentLinkSelect()
    expect(select.items).toEqual([
      {
        id: 2,
        name: 'Related documents',
        data_type: CustomFieldDataType.DocumentLink,
      },
    ])
    expect(select.allowNull).toBe(true)
    expect(select.value).toBeNull()

    const createSpy = jest
      .spyOn(TestBed.inject(MailRuleService), 'create')
      .mockImplementation((rule) => of(rule))
    component.save()
    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ assign_document_link_field: null })
    )
  })

  it('should save the selected document link field', () => {
    const createSpy = jest
      .spyOn(TestBed.inject(MailRuleService), 'create')
      .mockImplementation((rule) => of(rule))
    const select = getDocumentLinkSelect()
    select.value = 2
    select.onChange(2)

    component.save()

    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ assign_document_link_field: 2 })
    )
  })

  it('should load an existing document link field and allow clearing it', () => {
    const editFixture = TestBed.createComponent(MailRuleEditDialogComponent)
    const editComponent = editFixture.componentInstance
    editComponent.dialogMode.set(EditDialogMode.EDIT)
    editComponent.object = {
      ...component.objectForm.value,
      id: 1,
      assign_document_link_field: 2,
    }
    editFixture.detectChanges()

    const select = getDocumentLinkSelect(editFixture)
    expect(select.value).toBe(2)
    const updateSpy = jest
      .spyOn(TestBed.inject(MailRuleService), 'update')
      .mockImplementation((rule) => of(rule))
    select.value = null
    select.onChange(null)
    editComponent.save()

    expect(updateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1, assign_document_link_field: null })
    )
  })

  it('should keep the rule editable when there are no document link fields', () => {
    jest
      .spyOn(TestBed.inject(CustomFieldsService), 'listAll')
      .mockReturnValue(of({ count: 0, results: [] }))
    const emptyFixture = TestBed.createComponent(MailRuleEditDialogComponent)

    expect(() => emptyFixture.detectChanges()).not.toThrow()
    expect(getDocumentLinkSelect(emptyFixture).items).toEqual([])
    expect(getDocumentLinkSelect(emptyFixture).notFoundText).toBe(
      'No Document Link custom fields found'
    )
    expect(
      emptyFixture.componentInstance.objectForm.value.assign_document_link_field
    ).toBeNull()
  })

  it('should preserve an existing link field when custom fields cannot be loaded', () => {
    const error = new Error('Forbidden')
    jest
      .spyOn(TestBed.inject(CustomFieldsService), 'listAll')
      .mockReturnValue(throwError(() => error))
    const toastSpy = jest.spyOn(TestBed.inject(ToastService), 'showError')
    const editFixture = TestBed.createComponent(MailRuleEditDialogComponent)
    const editComponent = editFixture.componentInstance
    editComponent.dialogMode.set(EditDialogMode.EDIT)
    editComponent.object = {
      ...component.objectForm.value,
      id: 1,
      assign_document_link_field: 2,
    }
    editFixture.detectChanges()

    expect(toastSpy).toHaveBeenCalledWith(
      'Error retrieving custom fields',
      error
    )
    expect(getDocumentLinkSelect(editFixture).value).toBe(2)
    expect(getDocumentLinkSelect(editFixture).isPrivate).toBe(true)

    const updateSpy = jest
      .spyOn(TestBed.inject(MailRuleService), 'update')
      .mockImplementation((rule) => of(rule))
    editComponent.objectForm.get('name').setValue('Updated rule')
    editComponent.save()

    expect(updateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Updated rule',
        assign_document_link_field: 2,
      })
    )
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
