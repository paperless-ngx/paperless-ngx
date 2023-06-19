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
import { GroupEditDialogComponent } from './group-edit-dialog.component'
import { PermissionsSelectComponent } from '../../permissions-select/permissions-select.component'

describe('GroupEditDialogComponent', () => {
  let component: GroupEditDialogComponent
  let fixture: ComponentFixture<GroupEditDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        GroupEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PermissionsFormComponent,
        PermissionsSelectComponent,
      ],
      providers: [NgbActiveModal],
      imports: [
        HttpClientTestingModule,
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        NgbModule,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(GroupEditDialogComponent)
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
})
