import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MetadataCollapseComponent } from './metadata-collapse.component';

describe('MetadataCollapseComponent', () => {
  let component: MetadataCollapseComponent;
  let fixture: ComponentFixture<MetadataCollapseComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ MetadataCollapseComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(MetadataCollapseComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
