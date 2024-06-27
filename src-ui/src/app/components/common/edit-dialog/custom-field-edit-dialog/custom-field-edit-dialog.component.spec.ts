import { ComponentFixture, TestBed } from '@angular/core/testing'

import { CustomFieldEditDialogComponent } from './custom-field-edit-dialog.component'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('CustomFieldEditDialogComponent', () => {
  let component: CustomFieldEditDialogComponent
  let settingsService: SettingsService
  let fixture: ComponentFixture<CustomFieldEditDialogComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [
        CustomFieldEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        SafeHtmlPipe,
      ],
      imports: [FormsModule, ReactiveFormsModule, NgSelectModule, NgbModule],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(CustomFieldEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 99, username: 'user99' }
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

  it('should disable data type select on edit', () => {
    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    component.ngOnInit()
    expect(component.objectForm.get('data_type').disabled).toBeTruthy()
  })
})
