import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CustomShelfComponent } from './custom-shelf.component';

describe('CustomShelfComponent', () => {
  let component: CustomShelfComponent;
  let fixture: ComponentFixture<CustomShelfComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomShelfComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(CustomShelfComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
