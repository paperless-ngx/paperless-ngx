import { ComponentFixture, TestBed } from '@angular/core/testing'

import { LogoComponent } from './logo.component'
import { By } from '@angular/platform-browser'

describe('LogoComponent', () => {
  let component: LogoComponent
  let fixture: ComponentFixture<LogoComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [LogoComponent],
    })
    fixture = TestBed.createComponent(LogoComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support extra classes', () => {
    expect(fixture.debugElement.queryAll(By.css('.foo'))).toHaveLength(0)
    component.extra_classes = 'foo'
    fixture.detectChanges()
    expect(fixture.debugElement.queryAll(By.css('.foo'))).toHaveLength(1)
  })

  it('should support setting height', () => {
    expect(fixture.debugElement.query(By.css('svg')).attributes.height).toEqual(
      '6em'
    )
    component.height = '10em'
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('svg')).attributes.height).toEqual(
      '10em'
    )
  })
})
