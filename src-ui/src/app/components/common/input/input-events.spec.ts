import { provideHttpClient } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { Component } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormControl, ReactiveFormsModule } from '@angular/forms'
import { NumberComponent } from './number/number.component'
import { TextComponent } from './text/text.component'
import { TextAreaComponent } from './textarea/textarea.component'
import { UrlComponent } from './url/url.component'

@Component({
  imports: [
    ReactiveFormsModule,
    TextComponent,
    NumberComponent,
    TextAreaComponent,
    UrlComponent,
  ],
  template: `
    <pngx-input-text [formControl]="control" />
    <pngx-input-number [formControl]="control" [showAdd]="false" />
    <pngx-input-textarea [formControl]="control" />
    <pngx-input-url [formControl]="control" />
  `,
})
class InputEventsHostComponent {
  control = new FormControl<string | number | null>(null)
}

describe.each([
  ['text', 'pngx-input-text input', 'Edited text', 'Edited text'],
  ['number', 'pngx-input-number input', '42', 42],
  ['textarea', 'pngx-input-textarea textarea', 'Edited\ntext', 'Edited\ntext'],
  ['url', 'pngx-input-url input', 'https://example.com', 'https://example.com'],
])(
  '%s input events',
  (_type, selector: string, text: string, value: string | number) => {
    let fixture: ComponentFixture<InputEventsHostComponent>
    let control: FormControl<string | number | null>
    let input: HTMLInputElement | HTMLTextAreaElement

    beforeEach(() => {
      TestBed.configureTestingModule({
        imports: [InputEventsHostComponent],
        providers: [provideHttpClient(), provideHttpClientTesting()],
      })
      fixture = TestBed.createComponent(InputEventsHostComponent)
      control = fixture.componentInstance.control
    })

    async function render() {
      fixture.detectChanges()
      await fixture.whenStable()
      input = fixture.nativeElement.querySelector(selector)
    }

    it('updates the form while typing and marks it touched only on blur', async () => {
      await render()
      const changed = jest.fn()
      control.valueChanges.subscribe(changed)
      input.value = text
      input.dispatchEvent(new Event('input'))
      expect(control.value).toBe(value)
      expect(control.dirty).toBe(true)
      expect(control.touched).toBe(false)

      input.dispatchEvent(new Event('change'))
      input.dispatchEvent(new Event('blur'))
      expect(control.touched).toBe(true)
      expect(changed).toHaveBeenCalledTimes(1)
    })

    it('honors an explicit updateOn blur strategy', async () => {
      control = new FormControl<string | number | null>(null, {
        updateOn: 'blur',
      })
      fixture.componentInstance.control = control
      await render()
      input.value = text
      input.dispatchEvent(new Event('input'))
      expect(control.value).toBeNull()
      expect(control.pristine).toBe(true)

      input.dispatchEvent(new Event('blur'))
      expect(control.value).toBe(value)
      expect(control.dirty).toBe(true)
      expect(control.touched).toBe(true)
    })
  }
)
