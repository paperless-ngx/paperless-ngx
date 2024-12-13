import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbCollapseModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { MetadataCollapseComponent } from './metadata-collapse.component'

const metadata = [
  {
    namespace: 'http://ns.adobe.com/pdf/1.3/',
    prefix: 'pdf',
    key: 'Producer',
    value: 'pikepdf 2.2.0',
  },
  {
    namespace: 'http://ns.adobe.com/xap/1.0/',
    prefix: 'xmp',
    key: 'ModifyDate',
    value: '2020-12-21T08:42:26+00:00',
  },
]

describe('MetadataCollapseComponent', () => {
  let component: MetadataCollapseComponent
  let fixture: ComponentFixture<MetadataCollapseComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [MetadataCollapseComponent],
      providers: [],
      imports: [NgbCollapseModule, NgxBootstrapIconsModule.pick(allIcons)],
    }).compileComponents()

    fixture = TestBed.createComponent(MetadataCollapseComponent)
    component = fixture.componentInstance
  })

  it('should display metadata', () => {
    component.title = 'Foo'
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain('Foo')
  })

  it('should display metadata', () => {
    component.metadata = metadata
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'pikepdf 2.2.0'
    )
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'ModifyDate'
    )
  })
})
