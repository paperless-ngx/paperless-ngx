import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbTooltipModule } from '@ng-bootstrap/ng-bootstrap'
import { SwitchComponent } from './switch.component'

describe('SwitchComponent', () => {
  let component: SwitchComponent
  let fixture: ComponentFixture<SwitchComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgbTooltipModule,
        SwitchComponent,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(SwitchComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of checkbox', () => {
    input.checked = true
    input.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.value).toBeTruthy()

    input.checked = false
    input.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.value).toBeFalsy()
  })

  it('should correctly report unset', () => {
    component.value = null
    expect(component.isUnset).toBeTruthy()
    component.value = undefined
    expect(component.isUnset).toBeTruthy()
  })

  it('should support a compact layout', () => {
    component.compact = true
    component.title = 'Test switch'
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('.mb-3')).toBeNull()
    expect(fixture.nativeElement.querySelector('.row')).toBeNull()
    expect(input.getAttribute('aria-label')).toEqual('Test switch')
  })
})
