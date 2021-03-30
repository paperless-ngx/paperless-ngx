import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentASNComponentComponent } from './document-asncomponent.component';

describe('DocumentASNComponentComponent', () => {
  let component: DocumentASNComponentComponent;
  let fixture: ComponentFixture<DocumentASNComponentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentASNComponentComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentASNComponentComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
