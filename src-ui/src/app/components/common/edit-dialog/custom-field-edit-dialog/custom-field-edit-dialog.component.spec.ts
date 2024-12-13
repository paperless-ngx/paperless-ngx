import { ComponentFixture, TestBed } from '@angular/core/testing'

import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ElementRef, QueryList } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogMode } from '../edit-dialog.component'
import { CustomFieldEditDialogComponent } from './custom-field-edit-dialog.component'

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
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
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

  it('should initialize select options on edit', () => {
    component.dialogMode = EditDialogMode.EDIT
    component.object = {
      id: 1,
      name: 'Field 1',
      data_type: CustomFieldDataType.Select,
      extra_data: {
        select_options: [
          { label: 'Option 1', id: '123-xyz' },
          { label: 'Option 2', id: '456-abc' },
          { label: 'Option 3', id: '789-123' },
        ],
      },
    }
    fixture.detectChanges()
    component.ngOnInit()
    expect(
      component.objectForm.get('extra_data').get('select_options').value.length
    ).toBe(3)
  })

  it('should support add / remove select options', () => {
    component.dialogMode = EditDialogMode.CREATE
    fixture.detectChanges()
    component.ngOnInit()
    expect(
      component.objectForm.get('extra_data').get('select_options').value.length
    ).toBe(0)
    component.addSelectOption()
    expect(
      component.objectForm.get('extra_data').get('select_options').value.length
    ).toBe(1)
    component.addSelectOption()
    expect(
      component.objectForm.get('extra_data').get('select_options').value.length
    ).toBe(2)
    component.removeSelectOption(0)
    expect(
      component.objectForm.get('extra_data').get('select_options').value.length
    ).toBe(1)
  })

  it('should focus on last select option input', () => {
    const selectOptionInputs = component[
      'selectOptionInputs'
    ] as QueryList<ElementRef>
    component.dialogMode = EditDialogMode.CREATE
    component.objectForm.get('data_type').setValue(CustomFieldDataType.Select)
    component.ngOnInit()
    component.ngAfterViewInit()
    component.addSelectOption()
    fixture.detectChanges()
    expect(document.activeElement).toBe(selectOptionInputs.last.nativeElement)
  })
})
