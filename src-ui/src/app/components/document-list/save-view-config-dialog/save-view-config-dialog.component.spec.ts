import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbActiveModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap'
import { of } from 'rxjs'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { CheckComponent } from '../../common/input/check/check.component'
import { PermissionsFormComponent } from '../../common/input/permissions/permissions-form/permissions-form.component'
import { PermissionsGroupComponent } from '../../common/input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../../common/input/permissions/permissions-user/permissions-user.component'
import { TextComponent } from '../../common/input/text/text.component'
import { SaveViewConfigDialogComponent } from './save-view-config-dialog.component'

describe('SaveViewConfigDialogComponent', () => {
  let component: SaveViewConfigDialogComponent
  let fixture: ComponentFixture<SaveViewConfigDialogComponent>
  let modal: NgbActiveModal

  beforeEach(fakeAsync(() => {
    TestBed.configureTestingModule({
      providers: [
        NgbActiveModal,
        {
          provide: UserService,
          useValue: {
            listAll: () => of({ results: [] }),
          },
        },
        {
          provide: GroupService,
          useValue: {
            listAll: () => of({ results: [] }),
          },
        },
      ],
      imports: [
        NgbModalModule,
        FormsModule,
        ReactiveFormsModule,
        SaveViewConfigDialogComponent,
        TextComponent,
        CheckComponent,
        PermissionsFormComponent,
        PermissionsUserComponent,
        PermissionsGroupComponent,
      ],
    }).compileComponents()

    modal = TestBed.inject(NgbActiveModal)
    fixture = TestBed.createComponent(SaveViewConfigDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
    tick()
  }))

  it('should support default name', () => {
    const name = 'Tag: Inbox'
    let result
    component.saveClicked.subscribe((saveResult) => (result = saveResult))
    component.defaultName = name
    component.save()
    expect(component.defaultName).toEqual(name)
    expect(result).toEqual({
      name,
      showInSideBar: false,
      showOnDashboard: false,
    })
  })

  it('should support user input', () => {
    const name = 'Tag: Inbox'
    let result
    component.saveClicked.subscribe((saveResult) => (result = saveResult))

    const nameInput = fixture.debugElement
      .query(By.directive(TextComponent))
      .query(By.css('input'))
    nameInput.nativeElement.value = name
    component.saveViewConfigForm.get('name').patchValue(name) // normally done by angular

    const sidebarCheckInput = fixture.debugElement
      .queryAll(By.directive(CheckComponent))[0]
      .query(By.css('input'))
    sidebarCheckInput.nativeElement.checked = true
    component.saveViewConfigForm.get('showInSideBar').patchValue(true) // normally done by angular

    const dashboardCheckInput = fixture.debugElement
      .queryAll(By.directive(CheckComponent))[1]
      .query(By.css('input'))
    dashboardCheckInput.nativeElement.checked = true
    component.saveViewConfigForm.get('showOnDashboard').patchValue(true) // normally done by angular

    component.save()
    expect(result).toEqual({
      name,
      showInSideBar: true,
      showOnDashboard: true,
    })
  })

  it('should support permissions input', () => {
    const permissions = {
      owner: 10,
      set_permissions: {
        view: { users: [2], groups: [3] },
        change: { users: [4], groups: [5] },
      },
    }
    let result
    component.saveClicked.subscribe((saveResult) => (result = saveResult))
    component.saveViewConfigForm.get('permissions_form').patchValue(permissions)
    component.save()
    expect(result).toEqual({
      name: '',
      showInSideBar: false,
      showOnDashboard: false,
      permissions_form: permissions,
    })
  })

  it('should support default name', () => {
    const saveClickedSpy = jest.spyOn(component.saveClicked, 'emit')
    const modalCloseSpy = jest.spyOn(modal, 'close')
    component.cancel()
    expect(saveClickedSpy).not.toHaveBeenCalled()
    expect(modalCloseSpy).toHaveBeenCalled()
  })
})
