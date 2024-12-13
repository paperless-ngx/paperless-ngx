import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ColorSliderModule } from 'ngx-color/slider'
import { ColorComponent } from './color.component'

describe('ColorComponent', () => {
  let component: ColorComponent
  let fixture: ComponentFixture<ColorComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ColorComponent],
      providers: [],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgbPopoverModule,
        ColorSliderModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(ColorComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input', () => {
    input.value = '#ff0000'
    component.colorChanged(input.value)
    fixture.detectChanges()
    expect(component.value).toEqual('#ff0000')
  })

  it('should set swatch color', () => {
    const swatch: HTMLSpanElement = fixture.nativeElement.querySelector(
      'span.input-group-text'
    )
    expect(swatch.style.backgroundColor).toEqual('')
    component.value = '#ff0000'
    fixture.detectChanges()
    expect(swatch.style.backgroundColor).toEqual('rgb(255, 0, 0)')
  })

  it('should show color slider popover', () => {
    component.value = '#ff0000'
    input.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()
    expect(
      fixture.nativeElement.querySelector('ngb-popover-window')
    ).not.toBeUndefined()
    expect(
      fixture.nativeElement.querySelector('color-slider')
    ).not.toBeUndefined()
    fixture.nativeElement
      .querySelector('color-slider')
      .dispatchEvent(new Event('change'))
  })

  it('should allow randomize color and update value', () => {
    expect(component.value).toBeUndefined()
    component.randomize()
    expect(component.value).not.toBeUndefined()
  })
})
