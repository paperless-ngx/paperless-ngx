import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { UrlComponent } from './url.component'

describe('TextComponent', () => {
  let component: UrlComponent
  let fixture: ComponentFixture<UrlComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [UrlComponent],
      providers: [],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(UrlComponent)
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
})
