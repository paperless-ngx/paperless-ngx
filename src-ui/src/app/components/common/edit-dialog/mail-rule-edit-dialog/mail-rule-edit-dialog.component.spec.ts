import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of } from 'rxjs'
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
import { SettingsService } from 'src/app/services/settings.service'
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
                results: [
                  {
                    id: 1,
                    name: 'Subject Field',
                    data_type: CustomFieldDataType.String,
                  },
                  {
                    id: 2,
                    name: 'Date Field',
                    data_type: CustomFieldDataType.Date,
                  },
                  {
                    id: 3,
                    name: 'Integer Field',
                    data_type: CustomFieldDataType.Integer,
                  },
                  {
                    id: 4,
                    name: 'Monetary Field',
                    data_type: CustomFieldDataType.Monetary,
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

  it('should filter CustomField options by data_type for the mail metadata FK selects', () => {
    const stringIds = component.stringCustomFieldOptions().map((f) => f.id)
    const dateIds = component.dateCustomFieldOptions().map((f) => f.id)
    expect(stringIds).toEqual([1])
    expect(dateIds).toEqual([2])
  })

  it('should route each mail metadata select to the correctly filtered CustomField list', () => {
    fixture.detectChanges()
    const debugEls = fixture.debugElement.queryAll(By.css('pngx-input-select'))
    const bindingsByFormControl = Object.fromEntries(
      debugEls
        .map((el) => [
          el.attributes['formControlName'],
          el.componentInstance.items,
        ])
        .filter(([name]) => name)
    )
    expect(bindingsByFormControl['assign_subject_to']).toEqual(
      component.stringCustomFieldOptions()
    )
    expect(bindingsByFormControl['assign_sender_to']).toEqual(
      component.stringCustomFieldOptions()
    )
    expect(bindingsByFormControl['assign_recipient_to']).toEqual(
      component.stringCustomFieldOptions()
    )
    expect(bindingsByFormControl['assign_message_date_to']).toEqual(
      component.dateCustomFieldOptions()
    )
  })
})
