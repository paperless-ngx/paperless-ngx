import { ComponentFixture, TestBed } from '@angular/core/testing'
import { PermissionsSelectComponent } from './permissions-select.component'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import {
  PermissionAction,
  PermissionType,
} from 'src/app/services/permissions.service'
import { By } from '@angular/platform-browser'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

const permissions = [
  'add_document',
  'view_document',
  'change_document',
  'delete_document',
  'change_tag',
  'view_documenttype',
]

const inheritedPermissions = ['change_tag', 'view_documenttype']

describe('PermissionsSelectComponent', () => {
  let component: PermissionsSelectComponent
  let fixture: ComponentFixture<PermissionsSelectComponent>
  let permissionsChangeResult: Permissions
  let settingsService: SettingsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [PermissionsSelectComponent],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    fixture = TestBed.createComponent(PermissionsSelectComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    component.registerOnChange((r) => (permissionsChangeResult = r))
    fixture.detectChanges()
  })

  it('should create controls for all PermissionType and PermissionAction', () => {
    expect(Object.values(component.form.controls)).toHaveLength(
      Object.keys(PermissionType).length
    )
    for (var type in component.form.controls) {
      expect(
        Object.values(component.form.controls[type].controls)
      ).toHaveLength(Object.keys(PermissionAction).length)
    }
    // coverage
    component.registerOnTouched(() => {})
    component.setDisabledState(true)
  })

  it('should allow toggle all on / off', () => {
    component.ngOnInit()
    expect(component.typesWithAllActions.values).toHaveLength(0)
    component.toggleAll({ target: { checked: true } }, 'Tag')
    expect(component.typesWithAllActions).toContain('Tag')
    component.toggleAll({ target: { checked: false } }, 'Tag')
    expect(component.typesWithAllActions.values).toHaveLength(0)
  })

  it('should update on permissions set', () => {
    component.ngOnInit()
    component.writeValue(permissions)
    expect(permissionsChangeResult).toEqual(permissions)
    expect(component.typesWithAllActions).toContain('Document')
  })

  it('should update checkboxes on permissions set', () => {
    component.ngOnInit()
    component.writeValue(permissions)
    fixture.detectChanges()
    const input1 = fixture.debugElement.query(By.css('input#Document_Add'))
    expect(input1.nativeElement.checked).toBeTruthy()
    const input2 = fixture.debugElement.query(By.css('input#Tag_Change'))
    expect(input2.nativeElement.checked).toBeTruthy()
  })

  it('disable checkboxes when permissions are inherited', () => {
    component.ngOnInit()
    component.inheritedPermissions = inheritedPermissions
    expect(component.isInherited('Document', 'Add')).toBeFalsy()
    expect(component.isInherited('Document')).toBeFalsy()
    expect(component.isInherited('Tag', 'Change')).toBeTruthy()
    const input1 = fixture.debugElement.query(By.css('input#Document_Add'))
    expect(input1.nativeElement.disabled).toBeFalsy()
    const input2 = fixture.debugElement.query(By.css('input#Tag_Change'))
    expect(input2.nativeElement.disabled).toBeTruthy()
  })

  it('should exclude history permissions if disabled', () => {
    settingsService.set(SETTINGS_KEYS.AUDITLOG_ENABLED, false)
    fixture = TestBed.createComponent(PermissionsSelectComponent)
    component = fixture.componentInstance
    expect(component.allowedTypes).not.toContain('History')
  })
})
