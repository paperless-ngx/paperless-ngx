import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentAsnComponent } from './document-asn.component';

describe('DocumentASNComponentComponent', () => {
  let component: DocumentAsnComponent;
  let fixture: ComponentFixture<DocumentAsnComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentAsnComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentAsnComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
