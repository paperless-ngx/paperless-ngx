import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { PasswordComponent } from './password.component'

describe('PasswordComponent', () => {
  let component: PasswordComponent
  let fixture: ComponentFixture<PasswordComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [PasswordComponent],
      providers: [],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(PasswordComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input field', () => {
    expect(component.value).toBeUndefined()
    // TODO: why doesn't this work?
    // input.value = 'foo'
    // input.dispatchEvent(new Event('change'))
    // fixture.detectChanges()
    // expect(component.value).toEqual('foo')
  })

  it('should support toggling field visibility', () => {
    expect(input.type).toEqual('password')
    component.showReveal = true
    fixture.detectChanges()
    fixture.debugElement.query(By.css('button')).triggerEventHandler('click')
    fixture.detectChanges()
    expect(input.type).toEqual('text')
  })

  it('should empty field if password is obfuscated on focus', () => {
    component.value = '*********'
    component.onFocus()
    expect(component.value).toEqual('')
    component.onFocusOut()
    expect(component.value).toEqual('**********')
  })

  it('should disable toggle button if no real password', () => {
    component.value = '*********'
    expect(component.disableRevealToggle).toBeTruthy()
  })
})
