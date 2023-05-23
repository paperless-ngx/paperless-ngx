import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { EditDialogMode } from '../edit-dialog.component'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SelectComponent } from '../../input/select/select.component'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { TextComponent } from '../../input/text/text.component'
import { NgSelectModule } from '@ng-select/ng-select'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { MailRuleEditDialogComponent } from './mail-rule-edit-dialog.component'
import { NumberComponent } from '../../input/number/number.component'
import { TagsComponent } from '../../input/tags/tags.component'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { of } from 'rxjs'
import {
  MailAction,
  MailMetadataCorrespondentOption,
} from 'src/app/data/paperless-mail-rule'

describe('MailRuleEditDialogComponent', () => {
  let component: MailRuleEditDialogComponent
  let fixture: ComponentFixture<MailRuleEditDialogComponent>
  let accountService: MailAccountService
  let correspondentService: CorrespondentService
  let documentTypeService: DocumentTypeService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        MailRuleEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PermissionsFormComponent,
        NumberComponent,
        TagsComponent,
        SafeHtmlPipe,
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
      ],
      imports: [
        HttpClientTestingModule,
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(MailRuleEditDialogComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode = EditDialogMode.EDIT
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
