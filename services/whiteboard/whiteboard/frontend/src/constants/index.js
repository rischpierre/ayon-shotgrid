export const EntityType = Object.freeze({
    Shot: 'Shot', // match backend models.EntityType values
    Asset: 'Asset',
});

export const annotationColors= ['#c7cbe0', '#ffd166', '#ef476f', '#06d6a0', '#118ab2'];

// Backend uses lowercase: mon..fri
export const dayOrder = ['mon', 'tue', 'wed', 'thu', 'fri'];
export const dayTitle = {
    mon: 'Mon',
    tue: 'Tue',
    wed: 'Wed',
    thu: 'Thu',
    fri: 'Fri',
};
export const dayMap = {1: 'mon', 2: 'tue', 3: 'wed', 4: 'thu', 5: 'fri'};

// Weeks are w0..w3, where w0=current week
export const weekOrder = ['w0', 'w1', 'w2', 'w3'];
export const weekTitle = {
    w0: 'Current Week',
    w1: 'Next Week',
    w2: '3rd Week',
    w3: '4th Week',
};

export const DAY_COLORS = ['#c7cbe0', '#5b8def', '#50e3c2', '#f5a623', '#ff6b6b', '#b084eb'];
