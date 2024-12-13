import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbActiveModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap'
import { CheckComponent } from '../../common/input/check/check.component'
import { TextComponent } from '../../common/input/text/text.component'
import { SaveViewConfigDialogComponent } from './save-view-config-dialog.component'

describe('SaveViewConfigDialogComponent', () => {
  let component: SaveViewConfigDialogComponent
  let fixture: ComponentFixture<SaveViewConfigDialogComponent>
  let modal: NgbActiveModal

  beforeEach(fakeAsync(() => {
    TestBed.configureTestingModule({
      declarations: [
        SaveViewConfigDialogComponent,
        TextComponent,
        CheckComponent,
      ],
      providers: [NgbActiveModal],
      imports: [NgbModalModule, FormsModule, ReactiveFormsModule],
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

  it('should support default name', () => {
    const saveClickedSpy = jest.spyOn(component.saveClicked, 'emit')
    const modalCloseSpy = jest.spyOn(modal, 'close')
    component.cancel()
    expect(saveClickedSpy).not.toHaveBeenCalled()
    expect(modalCloseSpy).toHaveBeenCalled()
  })
})
