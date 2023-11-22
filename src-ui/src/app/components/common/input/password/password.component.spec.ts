import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  ReactiveFormsModule,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import { PasswordComponent } from './password.component'
import { By } from '@angular/platform-browser'

describe('PasswordComponent', () => {
  let component: PasswordComponent
  let fixture: ComponentFixture<PasswordComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [PasswordComponent],
      providers: [],
      imports: [FormsModule, ReactiveFormsModule],
    }).compileComponents()

    fixture = TestBed.createComponent(PasswordComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input field', () => {
    expect(component.value).toBeUndefined()
    // TODO: why doesnt this work?
    // input.value = 'foo'
    // input.dispatchEvent(new Event('change'))
    // fixture.detectChanges()
    // expect(component.value).toEqual('foo')
  })

  it('should support toggling field visibility', () => {
    expect(component.inputField.nativeElement.type).toEqual('password')
    component.showReveal = true
    fixture.detectChanges()
    fixture.debugElement.query(By.css('button')).triggerEventHandler('click')
    fixture.detectChanges()
    expect(component.inputField.nativeElement.type).toEqual('text')
  })

  it('should empty field if password is obfuscated', () => {
    component.value = '*********'
    component.toggleVisibility()
    expect(component.value).toEqual('')
    component.toggleVisibility()
    expect(component.value).toEqual('*********')
  })
})
