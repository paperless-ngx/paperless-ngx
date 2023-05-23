import { ComponentFixture, TestBed } from '@angular/core/testing'
import { TagComponent } from './tag.component'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import { By } from '@angular/platform-browser'

const tag: PaperlessTag = {
  id: 1,
  color: '#ff0000',
  name: 'Tag1',
}

describe('TagComponent', () => {
  let component: TagComponent
  let fixture: ComponentFixture<TagComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [TagComponent],
      providers: [],
      imports: [],
    }).compileComponents()

    fixture = TestBed.createComponent(TagComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create tag with background color', () => {
    component.tag = tag
    fixture.detectChanges()
    expect(
      fixture.debugElement.query(By.css('span')).nativeElement.style
        .backgroundColor
    ).toEqual('rgb(255, 0, 0)')
  })

  it('should handle private tags', () => {
    expect(
      fixture.debugElement.query(By.css('span')).nativeElement.textContent
    ).toEqual('Private')
  })

  it('should support clickable option', () => {
    component.tag = tag
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('a.badge'))).toBeNull()
    component.clickable = true
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('a.badge'))).not.toBeNull()
  })
})
